"""Treina o YOLO26s com uma única classe "ovo" (dataset gerado por preparar_dataset.py).

Cada treino vira uma run no MLflow (parâmetros, métricas por época, gráficos e best.pt).
Veja python/rastreio_mlflow.py; use --sem-mlflow para desligar.
"""

import argparse
import sys
from pathlib import Path

from ultralytics import YOLO

PYTHON_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PYTHON_DIR))


def com_mlflow(model, args):
    if args.sem_mlflow:
        return model
    from rastreio_mlflow import RastreadorTreino

    return RastreadorTreino(nome_run=args.nome_run).anexar(model)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", type=int, default=8, help='se der "CUDA out of memory", baixar para 4')
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--retomar", help="caminho de um last.pt para continuar um treino interrompido")
    parser.add_argument("--nome-run", help="nome da run no MLflow (padrão: nome da pasta do treino)")
    parser.add_argument("--sem-mlflow", action="store_true", help="não registrar o treino no MLflow")
    args = parser.parse_args()

    data = str(PYTHON_DIR / "datasets" / "ovos" / "data.yaml")

    if args.retomar:
        # data e save_dir novos: o checkpoint guarda os caminhos da máquina onde o treino começou.
        # A run do MLflow é retomada pelo mlflow_run_id.txt da pasta do treino.
        com_mlflow(YOLO(args.retomar), args).train(
            resume=True,
            data=data,
            save_dir=str(Path(args.retomar).resolve().parent.parent),
            batch=args.batch,
            workers=args.workers,
        )
    else:
        model = com_mlflow(YOLO("yolo26s.pt"), args)
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
