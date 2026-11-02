"""API e WebSocket do dashboard.

Fluxo de uma captura (manual ou automática), com um evento WebSocket a cada etapa:
pedido -> contando -> pronto (ou erro). A contagem é feita pelo applications/contador/servico_contagem.py;
o dashboard só pede a foto e recebe o resultado pelo MQTT. Contagens que chegam sem pedido do
dashboard (ex.: captura_mqtt.py, enviar_imagem.py) entram no histórico com origem "externa".
"""

import asyncio
import contextlib
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    estado = {"config": banco.ler_config(CONFIG_PADRAO), "proxima_auto": None, "etapa": None, "conf_ultimo": None}
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
