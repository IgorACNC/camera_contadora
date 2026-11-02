"""Envia uma imagem do PC para ovitrampa/cam1/foto e mostra a contagem devolvida pelo serviço."""

import argparse
import sys
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

TOPICO_FOTO = "ovitrampa/cam1/foto"
TOPICO_CONTAGEM = "ovitrampa/cam1/contagem"
TIMEOUT_S = 30


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("imagem", type=Path, help="caminho do arquivo a enviar")
    parser.add_argument("--host", default="localhost", help="endereço do broker MQTT")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()

    dados = args.imagem.read_bytes()
    recebida = threading.Event()
    resultado = {}

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Falha ao conectar no broker: {reason_code}", file=sys.stderr)
            return
        client.subscribe(TOPICO_CONTAGEM)

    def on_subscribe(client, userdata, mid, reason_codes, properties):
        # Só envia depois que a assinatura está ativa, para não perder a resposta.
        client.publish(TOPICO_FOTO, dados)

    def on_message(client, userdata, msg):
        resultado["json"] = msg.payload.decode()
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
        print("Timeout: o servico_contagem.py está rodando?", file=sys.stderr)
        return 1

    print(resultado["json"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
