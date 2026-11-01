"""Contagem de ovos com o YOLO treinado (mesmos parâmetros de contar_ovos.py)."""

import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

PYTHON_DIR = Path(__file__).resolve().parent.parent
CONF_SEM_AVALIACAO = 0.25
MAX_DET = 1000


def achar_modelo() -> Path | None:
    """O best.pt mais recente em python/runs/*/weights/."""
    candidatos = sorted((PYTHON_DIR / "runs").glob("*/weights/best.pt"), key=lambda p: p.stat().st_mtime)
    return candidatos[-1] if candidatos else None


@dataclass
class Resultado:
    ovos: int
    conf_media: float | None
    tempo_ms: float
    modo: str  # "yolo" ou "rotulos" (simulação sem modelo)


class Contador:
    def __init__(self, caminho_modelo: Path | None):
        self.caminho = caminho_modelo
        self.model = None
        self.erro: str | None = None
        self.conf_padrao = CONF_SEM_AVALIACAO
        if caminho_modelo is not None:
            arquivo_conf = caminho_modelo.parent / "conf_contagem.txt"
            if arquivo_conf.exists():
                self.conf_padrao = float(arquivo_conf.read_text())

    def carregar(self):
        """Carrega o modelo (lento: chamar fora do event loop)."""
        if self.caminho is None:
            self.erro = "nenhum best.pt em python/runs/*/weights/"
            return
        if not self.caminho.exists():
            self.erro = f"modelo não encontrado: {self.caminho}"
            return
        from ultralytics import YOLO  # import pesado: só quando há modelo

        self.model = YOLO(str(self.caminho))
        # Uma predição vazia para aquecer (a primeira chamada é bem mais lenta).
        self.model.predict(np.zeros((640, 640, 3), dtype=np.uint8), verbose=False)

    @property
    def pronto(self) -> bool:
        return self.model is not None

    def contar(self, foto: Path, anotada: Path, conf: float, rotulos=None) -> Resultado:
        """Conta os ovos de `foto` e salva a imagem com as caixas em `anotada`."""
        t0 = time.perf_counter()
        if self.model is not None:
            r = self.model.predict(source=str(foto), conf=conf, max_det=MAX_DET, verbose=False)[0]
            cv2.imwrite(str(anotada), r.plot(labels=False, conf=False, line_width=1))
            confs = r.boxes.conf.cpu().numpy()
            ovos, conf_media, modo = len(confs), (float(confs.mean()) if len(confs) else None), "yolo"
        elif rotulos is not None:
            # Simulação sem modelo: desenha as caixas do rótulo do dataset.
            img = cv2.imread(str(foto))
            h, w = img.shape[:2]
            for cx, cy, bw, bh in rotulos:
                x1, y1 = int((cx - bw / 2) * w), int((cy - bh / 2) * h)
                x2, y2 = int((cx + bw / 2) * w), int((cy + bh / 2) * h)
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 64, 0), 1)
            cv2.imwrite(str(anotada), img)
            ovos, conf_media, modo = len(rotulos), None, "rotulos"
        else:
            raise RuntimeError(self.erro or "modelo não carregado")
        return Resultado(ovos, conf_media, (time.perf_counter() - t0) * 1000, modo)
