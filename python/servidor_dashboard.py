"""Sobe o backend do dashboard (API + WebSocket) em http://localhost:8000.

Precisa do applications/contador/servico_contagem.py rodando: é ele que conta os ovos.

Exemplos (a partir da raiz do projeto):
  python/.venv/Scripts/python.exe python/servidor_dashboard.py
  python/.venv/Scripts/python.exe python/servidor_dashboard.py --mqtt-host 192.168.0.10
  python/.venv/Scripts/python.exe python/servidor_dashboard.py --simular   # sem câmera: fotos do dataset
"""

import argparse
from pathlib import Path

import uvicorn

from dashboard.servidor import Opcoes, criar_app

PYTHON_DIR = Path(__file__).resolve().parent
ZIP_DATASET = PYTHON_DIR / "aedes eggs.v6i.yolov8.zip"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mqtt-host", default="localhost", help="endereço do broker MQTT")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument(
        "--simular",
        action="store_true",
        help="publica fotos de teste do dataset no MQTT; precisa do servico_contagem.py rodando",
    )
    parser.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 para abrir o dashboard na rede local")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    opcoes = Opcoes(
        host=args.mqtt_host,
        port=args.mqtt_port,
        simular=args.simular,
        zip_dataset=ZIP_DATASET,
    )
    uvicorn.run(criar_app(opcoes), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
