"""API e WebSocket do dashboard.

Fluxo de uma captura (manual ou automática), com um evento WebSocket a cada etapa:
pedido -> contando -> pronto (ou erro). A contagem é feita pelo applications/contador/servico_contagem.py;
o dashboard só pede a foto e recebe o resultado pelo MQTT. Contagens que chegam sem pedido do
dashboard (ex.: captura_mqtt.py, enviar_imagem.py) entram no histórico com origem "externa".
"""

import asyncio
import contextlib
import io
import math
import os
import re
import smtplib
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from captura_mqtt import PASTA_CAPTURAS

from .banco import Banco
from .camera import CameraMQTT, CameraSimulada, ErroCaptura

PASTA_ANOTADAS = PASTA_CAPTURAS / "anotadas"
FRONT_DIST = PASTA_CAPTURAS.parent / "dashboard-web" / "dist"
TIMEOUT_CAPTURA_S = 30
HISTORICO_INICIAL = 200
CONFIG_PADRAO = {"auto_ativo": False, "intervalo_min": 10.0}
INTERVALO_ENVIO_S = 60


@dataclass
class Opcoes:
    host: str = "localhost"
    port: int = 1883
    simular: bool = False
    zip_dataset: Path | None = None


class Hub:
    """Clientes WebSocket conectados; `enviar` manda a mensagem para todos."""

    def __init__(self):
        self.clientes: set[WebSocket] = set()

    async def enviar(self, msg: dict):
        mortos = []
        for ws in list(self.clientes):
            try:
                await ws.send_json(msg)
            except Exception:
                mortos.append(ws)
        for ws in mortos:
            self.clientes.discard(ws)


class ConfigEntrada(BaseModel):
    auto_ativo: bool | None = None
    intervalo_min: float | None = Field(default=None, ge=0.5, le=24 * 60)


class RelatorioEntrada(BaseModel):
    email: str


def gerar_pdf_relatorio(capturas: list[dict], gerado_em: datetime) -> bytes:
    """Cria um PDF simples e imprimível com resumo e histórico de capturas."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("Dependência de PDF ausente. Instale python/requirements-dashboard.txt") from exc

    ok = [c for c in capturas if c["status"] == "ok"]
    ultimas10 = ok[-10:]
    ovos = [c["ovos"] for c in ok if c.get("ovos") is not None]
    media_ovos = sum(ovos) / len(ovos) if ovos else 0
    ultima = ok[-1] if ok else None
    hoje = gerado_em.date()
    capturas_hoje = [c for c in capturas if datetime.fromisoformat(c["inicio"]).date() == hoje]
    erros_hoje = sum(c["status"] == "erro" for c in capturas_hoje)

    def media_campo(registros, campo):
        valores = [c[campo] for c in registros if c.get(campo) is not None]
        return sum(valores) / len(valores) if valores else None

    def fmt_ms(valor):
        return f"{valor:.0f} ms" if valor is not None else "—"

    def fmt_pct(valor):
        return f"{valor * 100:.1f}%" if valor is not None else "—"

    media_ultimos10 = media_campo(ultimas10, "ovos")
    total_erros = sum(c["status"] == "erro" for c in capturas)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=15 * mm, leftMargin=15 * mm,
                            topMargin=14 * mm, bottomMargin=17 * mm, title="Relatório de ovos")
    estilos = getSampleStyleSheet()
    verde = colors.HexColor("#2f6b3f")
    texto = colors.HexColor("#1d211c")
    fraco = colors.HexColor("#6a7067")
    borda = colors.HexColor("#d9ded8")
    largura = landscape(A4)[0] - 30 * mm
    estilo_titulo = ParagraphStyle("TituloRelatorio", parent=estilos["Title"], fontName="Helvetica-Bold",
                                   fontSize=21, leading=25, textColor=verde, alignment=0, spaceAfter=2)
    estilo_meta = ParagraphStyle("MetaRelatorio", parent=estilos["Normal"], fontSize=9, textColor=fraco)
    estilo_secao = ParagraphStyle("SecaoRelatorio", parent=estilos["Heading2"], fontName="Helvetica-Bold",
                                  fontSize=12, leading=15, textColor=texto, spaceBefore=4, spaceAfter=7)
    estilo_rotulo = ParagraphStyle("RotuloIndicador", parent=estilos["Normal"], fontSize=8, leading=10,
                                   textColor=fraco)
    estilo_valor = ParagraphStyle("ValorIndicador", parent=estilos["Normal"], fontName="Helvetica-Bold",
                                  fontSize=13, leading=17, textColor=texto, wordWrap="CJK")
    elementos = [Paragraph("Relatório de análise de ovos", estilo_titulo),
                 Paragraph(f"Dashboard da ovitrampa cam1 &nbsp; · &nbsp; Gerado em "
                           f"{gerado_em.strftime('%d/%m/%Y às %H:%M:%S')}", estilo_meta),
                 Spacer(1, 7 * mm), Paragraph("Resumo geral", estilo_secao)]

    def cartao(rotulo, valor):
        conteudo = Table([
            [Paragraph(rotulo, estilo_rotulo)],
            [Paragraph(str(valor), estilo_valor)],
        ], colWidths=[largura_cartao - 18])
        conteudo.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 2), ("BOTTOMPADDING", (0, 1), (0, 1), 0),
        ]))
        return conteudo

    indicadores = [
        ("Capturas no histórico", str(len(capturas))), ("Capturas com sucesso", str(len(ok))),
        ("Capturas com erro", str(total_erros)), ("Capturas de hoje", f"{len(capturas_hoje)} ({erros_hoje} erro(s))"),
        ("Total de ovos detectados", str(sum(ovos))),
        ("Média de ovos por captura", f"{media_ovos:.1f}" if ovos else "—"),
        ("Ovos na última captura", str(ultima["ovos"]) if ultima and ultima.get("ovos") is not None else "—"),
        ("Média de ovos (últimas 10)", f"{media_ultimos10:.1f}" if media_ultimos10 is not None else "—"),
        ("Confiança média (última)", fmt_pct(ultima.get("conf_media") if ultima else None)),
        ("Tempo médio de captura¹", fmt_ms(media_campo(ultimas10, "tempo_captura_ms"))),
        ("Tempo médio de inferência¹", fmt_ms(media_campo(ultimas10, "tempo_inferencia_ms")),),
    ]
    largura_cartao = largura / 4
    linhas_cartoes = []
    for inicio in range(0, len(indicadores), 4):
        linha = [cartao(rotulo, valor) for rotulo, valor in indicadores[inicio:inicio + 4]]
        linha.extend([""] * (4 - len(linha)))
        linhas_cartoes.append(linha)
    resumo = Table(linhas_cartoes, colWidths=[largura_cartao] * 4, hAlign="LEFT")
    resumo.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f4f7f3")),
        ("BOX", (0, 0), (-1, -1), .6, borda), ("INNERGRID", (0, 0), (-1, -1), .5, borda),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.extend([resumo, Spacer(1, 3 * mm),
                      Paragraph("¹ Médias calculadas sobre as últimas 10 capturas bem-sucedidas.", estilo_meta),
                      Spacer(1, 6 * mm), Paragraph("Histórico de capturas", estilo_secao)])
    linhas = [["ID", "Data e hora", "Origem", "Ovos", "Confiança média", "Tempo de captura", "Tempo de inferência", "Status"]]
    for c in capturas:
        dt = datetime.fromisoformat(c["inicio"]).strftime("%d/%m/%Y %H:%M:%S")
        linhas.append([str(c["id"]), dt, {"auto": "Automática", "externa": "Externa"}.get(c["origem"], "Manual"),
                       str(c["ovos"] if c.get("ovos") is not None else "—"),
                       f"{c['conf_media'] * 100:.1f}%" if c.get("conf_media") is not None else "—",
                       f"{c['tempo_captura_ms']:.0f} ms" if c.get("tempo_captura_ms") is not None else "—",
                       f"{c['tempo_inferencia_ms']:.0f} ms" if c.get("tempo_inferencia_ms") is not None else "—",
                       "OK" if c["status"] == "ok" else "Erro" if c["status"] == "erro" else "Em andamento"])
    larguras = [12 * mm, 39 * mm, 28 * mm, 22 * mm, 34 * mm, 40 * mm, 42 * mm, largura - 217 * mm]
    tabela = Table(linhas, repeatRows=1, colWidths=larguras, hAlign="LEFT")
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), verde), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), .35, borda),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7f3")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elementos.append(tabela)

    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setStrokeColor(borda)
        canvas.line(15 * mm, 12 * mm, landscape(A4)[0] - 15 * mm, 12 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(fraco)
        canvas.drawString(15 * mm, 7 * mm, "Relatório de contagem de ovos · Ovitrampa cam1")
        canvas.drawRightString(landscape(A4)[0] - 15 * mm, 7 * mm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(elementos, onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()


def enviar_email_relatorio(destinatario: str, pdf: bytes):
    host = os.getenv("SMTP_HOST")
    usuario = os.getenv("SMTP_USER")
    senha = os.getenv("SMTP_PASSWORD")
    remetente = os.getenv("SMTP_FROM") or usuario or ""
    try:
        porta = int(os.getenv("SMTP_PORT", "587"))
    except ValueError as exc:
        raise RuntimeError("SMTP_PORT deve ser um número") from exc
    if not host or not remetente:
        raise RuntimeError("Configure SMTP_HOST e SMTP_FROM (ou SMTP_USER) nas variáveis de ambiente")
    msg = EmailMessage()
    msg["Subject"] = "Relatório de contagem de ovos"
    msg["From"] = remetente
    msg["To"] = destinatario
    msg.set_content("Olá! Segue em anexo o relatório PDF das contagens e métricas do dashboard.")
    msg.add_attachment(pdf, maintype="application", subtype="pdf", filename="relatorio_ovos.pdf")
    contexto = ssl.create_default_context()
    with smtplib.SMTP(host, porta, timeout=20) as servidor:
        servidor.starttls(context=contexto)
        if usuario and senha:
            servidor.login(usuario, senha)
        servidor.send_message(msg)


def ler_destinos() -> list[str]:
    """E-mails autorizados a receber o relatório (RELATORIO_DESTINOS, separados por vírgula)."""
    destinos = []
    for email in os.getenv("RELATORIO_DESTINOS", "").split(","):
        email = email.strip().lower()
        if email and email not in destinos:
            destinos.append(email)
    return destinos


def smtp_configurado() -> bool:
    return bool(os.getenv("SMTP_HOST") and (os.getenv("SMTP_FROM") or os.getenv("SMTP_USER")))


def agora() -> datetime:
    return datetime.now()


def _numero(x) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _nome_arquivo(caminho) -> str | None:
    # O JSON traz o caminho completo do serviço; o banco guarda só o nome (servido por /fotos).
    return re.split(r"[\\/]", caminho)[-1] if isinstance(caminho, str) else None


def campos_da_contagem(dados: dict) -> dict:
    """Colunas do banco a partir do JSON publicado pelo servico_contagem.py."""
    foto = _nome_arquivo(dados.get("arquivo"))
    arquivo = PASTA_CAPTURAS / foto if foto else None
    return {
        "status": "ok",
        "ovos": dados["ovos"],
        "conf_media": _numero(dados.get("conf_media")),
        "tempo_inferencia_ms": _numero(dados.get("tempo_inferencia_ms")),
        "foto": foto,
        "foto_anotada": _nome_arquivo(dados.get("anotada")),
        "bytes": arquivo.stat().st_size if arquivo and arquivo.is_file() else None,
        "modo": "yolo",
    }


def criar_app(opcoes: Opcoes) -> FastAPI:
    hub = Hub()
    banco = Banco(PASTA_CAPTURAS / "dashboard.db")
    trava = asyncio.Lock()
    trava_envio = asyncio.Lock()
    destinos = ler_destinos()
    estado = {"config": banco.ler_config(CONFIG_PADRAO), "proxima_auto": None, "etapa": None, "conf_ultimo": None,
              "ultimo_envio": None}
    loop_ref: dict = {}

    def agendar(coro_fn):
        # Chamado pela thread do paho-mqtt: agenda a corrotina no event loop.
        loop = loop_ref.get("loop")
        if loop is not None:
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(coro_fn()))

    def mudou_conexao():
        agendar(lambda: hub.enviar(status()))

    def resultado_externo(dados: dict):
        agendar(lambda: registrar_externa(dados))

    if opcoes.simular:
        camera = CameraSimulada(opcoes.host, opcoes.port, opcoes.zip_dataset, mudou_conexao, resultado_externo)
    else:
        camera = CameraMQTT(opcoes.host, opcoes.port, mudou_conexao, resultado_externo)

    def registrar_contagem(cid: int, dados: dict, **extras) -> dict:
        estado["conf_ultimo"] = _numero(dados.get("conf"))
        return banco.atualizar(cid, **campos_da_contagem(dados), **extras)

    def status() -> dict:
        e = camera.estado
        return {
            "tipo": "status",
            "simulacao": opcoes.simular,
            "mqtt": {"conectado": e.conectado, "erro": e.erro, **e.extras},
            "camera": {"estado": e.camera, "ultima_foto": e.ultima_foto},
            "servico": {"online": e.servico_online},
            "config": {**estado["config"], "conf_ultimo": estado["conf_ultimo"]},
            "proxima_auto": estado["proxima_auto"].isoformat(timespec="seconds") if estado["proxima_auto"] else None,
            "ocupado": trava.locked(),
            "etapa": estado["etapa"],
        }

    async def etapa(cid: int, nome: str, **dados):
        estado["etapa"] = {"id": cid, "etapa": nome, "em": agora().isoformat(timespec="milliseconds"), **dados}
        await hub.enviar({"tipo": "etapa", **estado["etapa"]})

    async def executar_captura(origem: str) -> dict:
        async with trava:
            inicio = agora()
            cid = banco.nova_captura(inicio.isoformat(timespec="seconds"), origem)
            await hub.enviar(status())
            await etapa(cid, "pedido", origem=origem)
            try:
                t0 = time.perf_counter()
                pedido = asyncio.ensure_future(asyncio.to_thread(camera.capturar, TIMEOUT_CAPTURA_S))
                # As falhas de pré-condição (broker ou serviço offline) acontecem na hora, antes de publicar:
                # nesse caso a etapa "contando" não aparece e o erro fica no lugar dela.
                await asyncio.wait({pedido}, timeout=0.1)
                if not pedido.done():
                    await etapa(cid, "contando")
                dados = await pedido
                total_ms = (time.perf_counter() - t0) * 1000

                inferencia = _numero(dados.get("tempo_inferencia_ms"))
                registro = registrar_contagem(
                    cid, dados, tempo_captura_ms=total_ms - inferencia if inferencia is not None else total_ms
                )
                await etapa(cid, "pronto", ovos=dados["ovos"])
            except Exception as e:  # qualquer falha vira uma captura com erro, sem derrubar o agendador
                msg = str(e) if isinstance(e, ErroCaptura) else f"{type(e).__name__}: {e}"
                registro = banco.atualizar(cid, status="erro", erro=msg)
                await etapa(cid, "erro", erro=msg)
            await hub.enviar({"tipo": "captura", "captura": registro})
        await hub.enviar(status())
        return registro

    async def registrar_externa(dados: dict):
        """Contagem que chegou sem pedido do dashboard: vira uma captura com origem "externa"."""
        cid = banco.nova_captura(agora().isoformat(timespec="seconds"), "externa")
        registro = registrar_contagem(cid, dados)
        await hub.enviar({"tipo": "captura", "captura": registro})
        await hub.enviar(status())

    async def agendador():
        """Dispara capturas automáticas no intervalo configurado."""
        while True:
            await asyncio.sleep(1)
            cfg = estado["config"]
            if not cfg["auto_ativo"]:
                estado["proxima_auto"] = None
                continue
            if estado["proxima_auto"] is None:
                estado["proxima_auto"] = agora() + timedelta(minutes=cfg["intervalo_min"])
                await hub.enviar(status())
            elif agora() >= estado["proxima_auto"] and not trava.locked():
                estado["proxima_auto"] = agora() + timedelta(minutes=cfg["intervalo_min"])
                await executar_captura("auto")

    @contextlib.asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        loop_ref["loop"] = asyncio.get_running_loop()
        banco.marcar_interrompidas()
        camera.iniciar()
        tarefas = [asyncio.create_task(agendador())]
        try:
            yield
        finally:
            for t in tarefas:
                t.cancel()
            camera.parar()

    app = FastAPI(title="Dashboard contador de ovos", lifespan=ciclo_de_vida)

    @app.get("/api/estado")
    async def api_estado():
        return status()

    @app.get("/api/capturas")
    async def api_capturas(limite: int = HISTORICO_INICIAL):
        return banco.ultimas(max(1, min(limite, 5000)))

    @app.get("/api/relatorio/destinos")
    async def api_destinos_relatorio():
        return {"destinos": destinos, "smtp_configurado": smtp_configurado()}

    @app.post("/api/relatorio/enviar")
    async def api_enviar_relatorio(entrada: RelatorioEntrada):
        if not destinos:
            raise HTTPException(503, "Nenhum destinatário configurado: defina RELATORIO_DESTINOS no terminal do servidor")
        email = entrada.email.strip().lower()
        if email not in destinos:
            raise HTTPException(403, "Destinatário não autorizado")
        if trava_envio.locked():
            raise HTTPException(429, "Já há um envio em andamento")
        async with trava_envio:
            if estado["ultimo_envio"] is not None:
                restante = INTERVALO_ENVIO_S - (time.monotonic() - estado["ultimo_envio"])
                if restante > 0:
                    raise HTTPException(429, f"Aguarde {math.ceil(restante)} s para enviar outro relatório")
            capturas = banco.ultimas(5000)
            try:
                pdf = await asyncio.to_thread(gerar_pdf_relatorio, capturas, agora())
                await asyncio.to_thread(enviar_email_relatorio, email, pdf)
            except RuntimeError as exc:
                raise HTTPException(503, str(exc)) from exc
            except (OSError, smtplib.SMTPException) as exc:
                raise HTTPException(502, f"Falha ao enviar o e-mail: {exc}") from exc
            estado["ultimo_envio"] = time.monotonic()
        return {"enviado": True, "email": email, "capturas": len(capturas)}

    @app.post("/api/capturar")
    async def api_capturar():
        if trava.locked():
            raise HTTPException(409, "Já há uma captura em andamento")
        return await executar_captura("manual")

    @app.put("/api/config")
    async def api_config(entrada: ConfigEntrada):
        novos = entrada.model_dump(exclude_unset=True)
        if "auto_ativo" in novos and novos["auto_ativo"] is None:
            del novos["auto_ativo"]
        estado["config"].update(novos)
        banco.salvar_config(estado["config"])
        if "intervalo_min" in novos or "auto_ativo" in novos:
            estado["proxima_auto"] = None  # o agendador recalcula a partir de agora
        msg = status()
        await hub.enviar(msg)
        return msg

    @app.get("/fotos/{tipo}/{nome}")
    async def api_foto(tipo: str, nome: str):
        if tipo not in ("original", "anotada") or not re.fullmatch(r"foto_[\w-]+\.jpg", nome):
            raise HTTPException(404)
        caminho = (PASTA_CAPTURAS if tipo == "original" else PASTA_ANOTADAS) / nome
        if not caminho.is_file():
            raise HTTPException(404)
        return FileResponse(caminho, media_type="image/jpeg")

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        hub.clientes.add(websocket)
        try:
            await websocket.send_json(status())
            await websocket.send_json({"tipo": "historico", "capturas": banco.ultimas(HISTORICO_INICIAL)})
            while True:
                await websocket.receive_text()  # o cliente não manda nada; só mantém a conexão
        except WebSocketDisconnect:
            pass
        finally:
            hub.clientes.discard(websocket)

    # Frontend já compilado (npm run build) servido na raiz, se existir.
    if FRONT_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONT_DIST, html=True), name="front")

    return app
