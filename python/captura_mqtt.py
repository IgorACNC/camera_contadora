"""Pede uma foto à ESP32-CAM via MQTT e salva o JPEG recebido."""

import argparse
import sys
import threading
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

TOPICO_PEDIDO = "ovitrampa/cam1/capturar"
TOPICO_FOTO = "ovitrampa/cam1/foto"
TIMEOUT_S = 15
PASTA_CAPTURAS = Path(__file__).resolve().parent.parent / "capturas"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="endereço do broker MQTT")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()

    recebida = threading.Event()
    foto = {}

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Falha ao conectar no broker: {reason_code}", file=sys.stderr)
            return
        client.subscribe(TOPICO_FOTO)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        # Só pede a foto depois que a assinatura está ativa, para não perder a resposta.
        client.publish(TOPICO_PEDIDO, b"1")

    def on_message(client, userdata, msg):
        foto["dados"] = msg.payload
        recebida.set()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message

    try:
        client.connect(args.host, args.port)
    except OSError as e:
        print(f"Não foi possível conectar em {args.host}:{args.port}: {e}", file=sys.stderr)
        return 1

    client.loop_start()
    ok = recebida.wait(TIMEOUT_S)
    client.loop_stop()
    client.disconnect()

    if not ok:
        print(
            f"Timeout: nenhuma foto recebida em {TIMEOUT_S} s. "
            "Confira se a ESP32-CAM está ligada e mostrou 'MQTT conectado' no Serial Monitor.",
            file=sys.stderr,
        )
        return 1

    PASTA_CAPTURAS.mkdir(exist_ok=True)
    caminho = PASTA_CAPTURAS / f"foto_{datetime.now():%Y%m%d_%H%M%S}.jpg"
    caminho.write_bytes(foto["dados"])
    print(f"Foto salva: {caminho} ({len(foto['dados'])} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
