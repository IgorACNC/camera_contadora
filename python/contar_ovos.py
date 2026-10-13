"""Conta ovos de Aedes em uma ou mais imagens com o modelo YOLO treinado."""

import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO

PYTHON_DIR = Path(__file__).resolve().parent
MODELO_PADRAO = PYTHON_DIR / "runs" / "ovos_yolo26s" / "weights" / "best.pt"
PASTA_ANOTADAS = PYTHON_DIR.parent / "capturas" / "anotadas"
CONF_SEM_AVALIACAO = 0.25


def conf_padrao(modelo):
    """conf escolhido por treino/avaliar_contagem.py, salvo ao lado do modelo."""
    arquivo = Path(modelo).parent / "conf_contagem.txt"
    if arquivo.exists():
        return float(arquivo.read_text())
    print(f"Aviso: {arquivo} não existe (rode treino/avaliar_contagem.py); usando conf={CONF_SEM_AVALIACAO}")
    return CONF_SEM_AVALIACAO


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("imagens", nargs="+", help="caminhos das imagens")
    parser.add_argument("--modelo", default=str(MODELO_PADRAO))
    parser.add_argument("--conf", type=float, help="limiar de confiança (padrão: o escolhido na avaliação)")
    args = parser.parse_args()

    conf = args.conf if args.conf is not None else conf_padrao(args.modelo)
    model = YOLO(args.modelo)
    PASTA_ANOTADAS.mkdir(parents=True, exist_ok=True)

    for r in model.predict(source=args.imagens, conf=conf, max_det=1000, stream=True, verbose=False):
        n = len(r.boxes)
        saida = PASTA_ANOTADAS / Path(r.path).name
        cv2.imwrite(str(saida), r.plot(labels=False, conf=False, line_width=1))
        print(f"{r.path}: {n} ovos (anotada em {saida})")


if __name__ == "__main__":
    main()
