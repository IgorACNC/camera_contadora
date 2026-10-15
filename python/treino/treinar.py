"""Treina o YOLO26s com uma única classe "ovo" (dataset gerado por preparar_dataset.py)."""

import argparse
from pathlib import Path

from ultralytics import YOLO

PYTHON_DIR = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, default=8, help='se der "CUDA out of memory", baixar para 4')
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retomar", help="caminho de um last.pt para continuar um treino interrompido")
    args = parser.parse_args()

    data = str(PYTHON_DIR / "datasets" / "ovos" / "data.yaml")

    if args.retomar:
        # data e save_dir novos: o checkpoint guarda os caminhos da máquina onde o treino começou
        YOLO(args.retomar).train(
            resume=True,
            data=data,
            save_dir=str(Path(args.retomar).resolve().parent.parent),
            batch=args.batch,
            workers=args.workers,
        )
    else:
        model = YOLO("yolo26s.pt")
        model.train(
            data=data,
            imgsz=640,
            epochs=150,
            patience=30,
            batch=args.batch,
            flipud=0.5,  # ovo não tem "lado de cima"
            max_det=1000,
            workers=args.workers,
            cache="ram",
            seed=0,
            project=str(PYTHON_DIR / "runs"),
            name="ovos_yolo26s",
            # amp=False,  # descomentar se as perdas virarem nan ou a mAP ficar em 0
        )
