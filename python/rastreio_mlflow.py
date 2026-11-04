"""Rastreamento dos treinos e registro do modelo de contagem de ovos no MLflow.

- `configurar()`: aponta para o servidor/banco do MLflow e escolhe o experimento.
- `RastreadorTreino`: callbacks da ultralytics que registram parâmetros, métricas por época,
  gráficos e pesos de um treino YOLO, ao vivo.
- `registrar_treino_existente()`: registra um treino já feito a partir da pasta runs/<nome>/.
- `registrar_modelo()`: publica best.pt + conf_contagem.txt como modelo pyfunc no Model Registry.
- `resolver_modelo()`: aceita um caminho de .pt ou uma URI models:/ e devolve o caminho do best.pt.

Padrões (sobrescritos pelas variáveis de ambiente de mesmo nome do MLflow):
- MLFLOW_TRACKING_URI: sqlite:///<repo>/python/mlflow.db (com SQLite, artefatos em mlruns/ ao lado do .db)
- MLFLOW_EXPERIMENT_NAME: contagem-ovos-aedes
"""

import csv
import functools
import logging
import os
import re
import sys
import warnings
from importlib import metadata
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
# Avisos do MLflow que não se aplicam aqui. No PowerShell 5.1, qualquer texto no stderr de um .exe
# aparece em vermelho como NativeCommandError, parecendo uma falha.
# - input_example: a assinatura do modelo é definida à mão em registrar_modelo().
warnings.filterwarnings("ignore", message=r".*An input example was not provided.*")

import mlflow  # noqa: E402

# - CloudPickle: o modelo é gerado e carregado pelo próprio projeto, não vem de fora.
logging.getLogger("mlflow.pyfunc").addFilter(lambda r: "CloudPickle" not in r.getMessage())

PYTHON_DIR = Path(__file__).resolve().parent
URI_PADRAO = f"sqlite:///{(PYTHON_DIR / 'mlflow.db').as_posix()}"
EXPERIMENTO_PADRAO = "contagem-ovos-aedes"
MODELO_REGISTRADO = "contador-ovos-aedes"
ARQUIVO_RUN_ID = "mlflow_run_id.txt"  # gravado na pasta do treino, liga treino, avaliação e registro
ARQUIVO_CONF = "conf_contagem.txt"
MAX_DET = 1000
GRAFICOS = ("*.png", "*.jpg", "results.csv", "args.yaml")


def configurar():
    """Define a tracking URI e o experimento. Devolve o experimento ativo."""
    uri = os.environ.get("MLFLOW_TRACKING_URI") or URI_PADRAO
    mlflow.set_tracking_uri(uri)
    nome = os.environ.get("MLFLOW_EXPERIMENT_NAME") or EXPERIMENTO_PADRAO
    if mlflow.get_experiment_by_name(nome) is None and uri.startswith("sqlite:///"):
        # Com SQLite, o padrão do MLflow é ./mlruns relativo ao diretório atual, que muda conforme
        # de onde o script roda: fixa os artefatos em mlruns/ ao lado do arquivo .db.
        artefatos = Path(uri.removeprefix("sqlite:///")).resolve().parent / "mlruns"
        artefatos.mkdir(parents=True, exist_ok=True)
        mlflow.create_experiment(nome, artifact_location=artefatos.as_uri())
    return mlflow.set_experiment(nome)


def nome_metrica(chave: str) -> str:
    """O MLflow não aceita parênteses: 'metrics/mAP50(B)' -> 'metrics/mAP50B'."""
    return re.sub(r"[^\w.\- /:]", "", chave)


def run_id_salvo(pasta_treino) -> str | None:
    arquivo = Path(pasta_treino) / ARQUIVO_RUN_ID
    if not arquivo.exists():
        return None
    run_id = arquivo.read_text().strip()
    try:
        mlflow.get_run(run_id)  # o arquivo pode ser de outra máquina/banco
    except Exception:
        return None
    return run_id


def _salvar_run_id(pasta_treino, run_id):
    pasta = Path(pasta_treino)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ARQUIVO_RUN_ID).write_text(run_id + "\n")


def _registrar_graficos(pasta_treino):
    pasta = Path(pasta_treino)
    for padrao in GRAFICOS:
        for arquivo in sorted(pasta.glob(padrao)):
            mlflow.log_artifact(str(arquivo), artifact_path="treino")


def _sem_derrubar_treino(func):
    """Uma falha do MLflow não pode jogar fora horas de treino: avisa e segue."""

    @functools.wraps(func)
    def envoltorio(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"[MLflow] aviso: {func.__name__} falhou: {e}", file=sys.stderr)

    return envoltorio


class RastreadorTreino:
    """Callbacks que registram um treino da ultralytics numa run do MLflow.

    Ao retomar um treino (--retomar), a run gravada em <pasta do treino>/mlflow_run_id.txt é
    reaberta e as épocas continuam no mesmo gráfico.
    """

    def __init__(self, nome_run: str | None = None, tags: dict | None = None):
        self.nome_run = nome_run
        self.tags = tags or {}

    def anexar(self, model):
        model.add_callback("on_pretrain_routine_start", self._inicio)
        model.add_callback("on_fit_epoch_end", self._fim_epoca)
        model.add_callback("on_train_end", self._fim_treino)
        return model

    @staticmethod
    def _remover_integracao_nativa(trainer):
        # A ultralytics tem um callback de MLflow próprio, ligado por padrão quando o mlflow está
        # instalado. Ele criaria uma segunda run, em outro lugar: remove só neste processo.
        for evento, funcs in trainer.callbacks.items():
            trainer.callbacks[evento] = [f for f in funcs if not f.__module__.endswith("callbacks.mlflow")]

    @_sem_derrubar_treino
    def _inicio(self, trainer):
        self._remover_integracao_nativa(trainer)
        configurar()
        run_id = run_id_salvo(trainer.save_dir)
        if mlflow.active_run():
            mlflow.end_run()
        if run_id:
            mlflow.start_run(run_id=run_id)
            print(f"[MLflow] retomando a run {run_id}")
        else:
            run = mlflow.start_run(run_name=self.nome_run or Path(trainer.save_dir).name)
            mlflow.log_params({k: str(v) for k, v in vars(trainer.args).items()})
            mlflow.set_tags({"modelo_base": str(trainer.args.model), "tarefa": "contagem de ovos", **self.tags})
            _salvar_run_id(trainer.save_dir, run.info.run_id)
            print(f"[MLflow] run {run.info.run_id} em {mlflow.get_tracking_uri()}")

    @_sem_derrubar_treino
    def _fim_epoca(self, trainer):
        if getattr(self, "_loop_terminou", False):
            # Depois do laço, o final_eval valida o best.pt e dispara este callback de novo:
            # registra como métricas do melhor modelo, sem criar uma "época" a mais.
            mlflow.log_metrics({"melhor/" + nome_metrica(k).split("/")[-1]: float(v) for k, v in trainer.metrics.items()})
            return
        self._loop_terminou = bool(trainer.stop)  # o trainer marca stop antes do callback da última época
        metricas = {
            **trainer.label_loss_items(trainer.tloss, prefix="train"),
            **trainer.metrics,
            **trainer.lr,
        }
        mlflow.log_metrics(
            {nome_metrica(k): float(v) for k, v in metricas.items()}, step=trainer.epoch + 1
        )

    @_sem_derrubar_treino
    def _fim_treino(self, trainer):
        if not mlflow.active_run():
            return
        _registrar_graficos(trainer.save_dir)
        if Path(trainer.best).exists():
            mlflow.log_artifact(str(trainer.best), artifact_path="pesos")
        mlflow.end_run()


def registrar_treino_existente(pasta_treino) -> str:
    """Registra um treino já feito (args.yaml, results.csv, gráficos e best.pt). Devolve o run_id.

    Se a pasta já tiver uma run registrada neste banco, só devolve o run_id dela.
    """
    import yaml

    pasta = Path(pasta_treino)
    configurar()
    run_id = run_id_salvo(pasta)
    if run_id:
        print(f"[MLflow] {pasta.name} já registrado: run {run_id}")
        return run_id

    with mlflow.start_run(run_name=pasta.name) as run:
        args = yaml.safe_load((pasta / "args.yaml").read_text(encoding="utf-8"))
        mlflow.log_params({k: str(v) for k, v in args.items()})
        mlflow.set_tags(
            {"modelo_base": str(args.get("model")), "tarefa": "contagem de ovos", "origem": "importado de runs/"}
        )
        with open(pasta / "results.csv", newline="", encoding="utf-8") as f:
            for linha in csv.DictReader(f):
                linha = {k.strip(): v for k, v in linha.items()}
                epoca = int(float(linha.pop("epoch")))
                linha.pop("time", None)
                mlflow.log_metrics({nome_metrica(k): float(v) for k, v in linha.items() if v}, step=epoca)
        _registrar_graficos(pasta)
        best = pasta / "weights" / "best.pt"
        if best.exists():
            mlflow.log_artifact(str(best), artifact_path="pesos")
        _salvar_run_id(pasta, run.info.run_id)
        print(f"[MLflow] {pasta.name} registrado: run {run.info.run_id}")
        return run.info.run_id


class ContadorOvos(mlflow.pyfunc.PythonModel):
    """Modelo pyfunc: recebe caminhos de imagens e devolve o número de ovos de cada uma.

    Entrada: DataFrame com a coluna "imagem" (caminho do arquivo).
    Saída: DataFrame com "ovos" e "conf_media" (média das confianças; NaN sem ovos).
    O limiar de confiança é o conf_contagem.txt escolhido por treino/avaliar_contagem.py.
    """

    # Sem type hints no predict, o MLflow avisaria a cada import; a assinatura já vem do registro.
    _skip_type_hint_validation = True

    def load_context(self, context):
        from ultralytics import YOLO

        self.modelo = YOLO(context.artifacts["pesos"])
        self.conf = float(Path(context.artifacts["conf"]).read_text())

    def predict(self, context, model_input, params=None):
        import pandas as pd

        imagens = list(model_input["imagem"]) if hasattr(model_input, "columns") else list(model_input)
        conf = float((params or {}).get("conf", self.conf))
        linhas = []
        for r in self.modelo.predict(source=imagens, conf=conf, max_det=MAX_DET, stream=True, verbose=False):
            n = len(r.boxes)
            linhas.append({"ovos": n, "conf_media": float(r.boxes.conf.mean()) if n else float("nan")})
        return pd.DataFrame(linhas, columns=["ovos", "conf_media"])


def _versao(pacote):
    try:
        return metadata.version(pacote)
    except metadata.PackageNotFoundError:
        return None


def registrar_modelo(pesos, run_id: str, alias: str | None = None):
    """Loga best.pt + conf_contagem.txt como modelo pyfunc na run e cria uma versão no Registry.

    Devolve a versão registrada (str). Com `alias` (ex.: "producao"), move o alias para ela.
    """
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, ParamSchema, ParamSpec, Schema

    pesos = Path(pesos)
    arquivo_conf = pesos.parent / ARQUIVO_CONF
    if not arquivo_conf.exists():
        raise FileNotFoundError(f"{arquivo_conf} não existe: rode treino/avaliar_contagem.py antes de registrar")
    conf = float(arquivo_conf.read_text())

    assinatura = ModelSignature(
        inputs=Schema([ColSpec("string", "imagem")]),
        outputs=Schema([ColSpec("long", "ovos"), ColSpec("double", "conf_media")]),
        params=ParamSchema([ParamSpec("conf", "double", conf)]),
    )
    requisitos = [f"{p}=={v}" if v else p for p, v in (("ultralytics", _versao("ultralytics")), ("mlflow", _versao("mlflow")))]

    configurar()
    with mlflow.start_run(run_id=run_id):
        mlflow.log_metric("conf_contagem", conf)
        info = mlflow.pyfunc.log_model(
            name="modelo",
            python_model=ContadorOvos(),
            artifacts={"pesos": str(pesos), "conf": str(arquivo_conf)},
            code_paths=[__file__],
            signature=assinatura,
            pip_requirements=requisitos,
            registered_model_name=MODELO_REGISTRADO,
            metadata={"conf_contagem": conf, "max_det": MAX_DET, "classes": ["ovo"]},
        )
    versao = str(info.registered_model_version)
    cliente = mlflow.MlflowClient()
    cliente.set_model_version_tag(MODELO_REGISTRADO, versao, "conf_contagem", f"{conf:.2f}")
    if alias:
        cliente.set_registered_model_alias(MODELO_REGISTRADO, alias, versao)
    print(f"[MLflow] {MODELO_REGISTRADO} versão {versao}" + (f" (alias @{alias})" if alias else ""))
    return versao


def resolver_modelo(modelo: str) -> str:
    """Caminho local do best.pt. Aceita um caminho ou uma URI do MLflow (models:/... ou runs:/...).

    Com URI, baixa o modelo; o conf_contagem.txt vem junto, ao lado do best.pt.
    """
    if not modelo.startswith(("models:/", "runs:/")):
        return modelo
    configurar()
    local = Path(mlflow.artifacts.download_artifacts(artifact_uri=modelo))
    pesos = local / "artifacts" / "best.pt"
    if not pesos.exists():
        raise FileNotFoundError(f"{modelo} não tem artifacts/best.pt (é um modelo de {MODELO_REGISTRADO}?)")
    print(f"[MLflow] {modelo} -> {pesos}")
    return str(pesos)
