"""Treina o YOLO26s com uma única classe "ovo" (dataset gerado por preparar_dataset.py)."""

from pathlib import Path

from ultralytics import YOLO

PYTHON_DIR = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    model = YOLO("yolo26s.pt")
    model.train(
        data=str(PYTHON_DIR / "datasets" / "ovos" / "data.yaml"),
        imgsz=640,
        epochs=150,
        patience=30,
        batch=8,  # se der "CUDA out of memory", baixar para 4
        flipud=0.5,  # ovo não tem "lado de cima"
        max_det=1000,
        workers=2,
        cache="ram",
        seed=0,
        project=str(PYTHON_DIR / "runs"),
        name="ovos_yolo26s",
        # amp=False,  # descomentar se as perdas virarem nan ou a mAP ficar em 0
    )
