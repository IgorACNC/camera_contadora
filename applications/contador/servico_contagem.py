"""Serviço que conta ovos em cada foto publicada em ovitrampa/cam1/foto e publica o resultado.

Para cada JPEG recebido: salva a original em capturas/, roda o YOLO, salva a anotada em
capturas/anotadas/ e publica um JSON em ovitrampa/cam1/contagem.
"""

import argparse
import json
import queue
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import paho.mqtt.client as mqtt
from ultralytics import YOLO

TOPICO_FOTO = "ovitrampa/cam1/foto"
TOPICO_CONTAGEM = "ovitrampa/cam1/contagem"
RAIZ = Path(__file__).resolve().parents[2]
MODELO_PADRAO = RAIZ / "python" / "runs" / "ovos_yolo26s-2" / "weights" / "best.pt"
PASTA_CAPTURAS = RAIZ / "capturas"
PASTA_ANOTADAS = PASTA_CAPTURAS / "anotadas"
CONF_SEM_AVALIACAO = 0.25


def conf_padrao(modelo):
    """conf escolhido por python/treino/avaliar_contagem.py, salvo ao lado do modelo."""
    arquivo = Path(modelo).parent / "conf_contagem.txt"
    if arquivo.exists():
        return float(arquivo.read_text())
    print(f"Aviso: {arquivo} não existe (rode python/treino/avaliar_contagem.py); usando conf={CONF_SEM_AVALIACAO}")
    return CONF_SEM_AVALIACAO


def processar(payload, model, conf, client):
    # O tópico é anônimo: qualquer um pode publicar nele, então o payload precisa ser validado.
    img = cv2.imdecode(np.frombuffer(payload, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print(f"Payload inválido ({len(payload)} bytes), ignorado")
        return

    agora = datetime.now()
    nome = f"foto_{agora:%Y%m%d_%H%M%S_%f}.jpg"
    original = PASTA_CAPTURAS / nome
    anotada = PASTA_ANOTADAS / nome
    original.write_bytes(payload)

    r = model.predict(img, conf=conf, max_det=1000, verbose=False)[0]
    n = len(r.boxes)
    cv2.imwrite(str(anotada), r.plot(labels=False, conf=False, line_width=1))

    altura, largura = img.shape[:2]
    horario = agora.isoformat(timespec="seconds")
    resultado = {
        "ovos": n,
        "conf": conf,
        "horario": horario,
        "arquivo": str(original),
        "anotada": str(anotada),
        "largura": largura,
        "altura": altura,
    }
    client.publish(TOPICO_CONTAGEM, json.dumps(resultado))
    print(f"{horario} {largura}x{altura}: {n} ovos -> {anotada}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="endereço do broker MQTT")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--modelo", default=str(MODELO_PADRAO))
    parser.add_argument("--conf", type=float, help="limiar de confiança (padrão: o escolhido na avaliação)")
    args = parser.parse_args()

    conf = args.conf if args.conf is not None else conf_padrao(args.modelo)
    model = YOLO(args.modelo)
    print(f"Modelo carregado: {args.modelo} conf={conf}")
    PASTA_ANOTADAS.mkdir(parents=True, exist_ok=True)

    fila = queue.Queue()

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"Falha ao conectar no broker: {reason_code}", file=sys.stderr)
            return
        # Assinar aqui faz a assinatura voltar sozinha após uma reconexão.
        client.subscribe(TOPICO_FOTO)
        print(f"Aguardando fotos em {TOPICO_FOTO}")

    def on_message(client, userdata, msg):
        # Só enfileira: a inferência roda no laço principal, sem travar a rede do paho.
        fila.put(msg.payload)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(args.host, args.port)
    except OSError as e:
        print(f"Não foi possível conectar em {args.host}:{args.port}: {e}", file=sys.stderr)
        return 1

    client.loop_start()
    try:
        while True:
            try:
                payload = fila.get(timeout=0.5)  # timeout para o Ctrl+C funcionar no Windows
            except queue.Empty:
                continue
            processar(payload, model, conf, client)
    except KeyboardInterrupt:
        print("Encerrando...")
    finally:
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
