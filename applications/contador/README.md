# Serviço de contagem de ovos

Serviço Python sempre ligado. Cada foto que chega pelo MQTT passa pelo YOLO26s, e o número de ovos volta pelo MQTT.

```
captura_mqtt.py ── ovitrampa/cam1/capturar ──► ESP32-CAM
ESP32-CAM ──────── ovitrampa/cam1/foto ──────► servico_contagem.py ──► YOLO26s
servico_contagem.py ── ovitrampa/cam1/contagem (JSON) ──► quem assinar
```

| Tópico | Conteúdo |
|--------|----------|
| `ovitrampa/cam1/capturar` | Pedido de foto para a câmera (qualquer payload) |
| `ovitrampa/cam1/foto` | JPEG, vindo da câmera ou do `enviar_imagem.py` |
| `ovitrampa/cam1/contagem` | Resultado em JSON |

Para cada foto recebida, o serviço:
- salva a original em `capturas/foto_AAAAMMDD_HHMMSS_ffffff.jpg`;
- salva a anotada em `capturas/anotadas/`, com o mesmo nome;
- ignora qualquer payload que não seja imagem, mostrando "Payload inválido".

## Formato do JSON

```json
{
  "ovos": 42,
  "conf": 0.4,
  "horario": "2026-10-29T14:03:12",
  "arquivo": "A:\\CameraWebServer\\capturas\\foto_20261029_140312_123456.jpg",
  "anotada": "A:\\CameraWebServer\\capturas\\anotadas\\foto_20261029_140312_123456.jpg",
  "largura": 800,
  "altura": 600
}
```

## Como rodar (da raiz `A:\CameraWebServer`)

```
# Terminal 1 — serviço (deixar aberto)
python\.venv\Scripts\python.exe applications\contador\servico_contagem.py

# Terminal 2 — teste sem câmera
python\.venv\Scripts\python.exe applications\contador\enviar_imagem.py python\datasets\ovos\test\images\<arquivo>.jpg

# Terminal 2 — com a câmera ligada (o serviço conta sozinho)
python\.venv\Scripts\python.exe python\captura_mqtt.py

# Ver os resultados chegando (opcional)
A:\Mosquitto\mosquitto_sub.exe -t ovitrampa/cam1/contagem -v
```

Opções do serviço: `--host`, `--port`, `--modelo` (padrão `python/runs/ovos_yolo26s-2/weights/best.pt`) e `--conf` (padrão: o valor de `conf_contagem.txt`, ao lado do modelo).
