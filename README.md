# camera_contadora — ESP32-CAM para ovitrampas

Firmware da ESP32-CAM (AI Thinker + OV2640). Ele é baseado no exemplo oficial `CameraWebServer` e serve fotos por HTTP. Essas fotos alimentam um modelo YOLO em Python que conta ovos de *Aedes aegypti*.

## 1. Configurar o Wi-Fi

As credenciais ficam em `secrets.h`, que está no `.gitignore` e não vai para o repositório. Se o arquivo não existir (por exemplo, num clone novo), crie-o na raiz do projeto:

```cpp
#ifndef SECRETS_H
#define SECRETS_H

#define WIFI_SSID     "nome_da_rede"
#define WIFI_PASSWORD "senha_da_rede"

#endif  // SECRETS_H
```

A rede precisa ser **2.4 GHz**, porque a ESP32 não conecta em redes de 5 GHz.

## 2. Compilar e gravar

**Arduino IDE** (2.3.x, core esp32 3.3.x):

- Placa: `AI Thinker ESP32-CAM`
- Partition Scheme: `Huge APP (3MB No OTA/1MB SPIFFS)`
- Upload Speed: `115200`
- Porta: `COM12` (programador ESP32-CAM-MB, chip CH340)

**arduino-cli** (alternativa; confira o FQBN antes de usar):

```sh
arduino-cli compile --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app .
arduino-cli upload  -p COM12 --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app .
```

## 3. Descobrir o IP da câmera

1. Abra o Serial Monitor em **115200 baud**.
2. Aperte o botão **RST** da placa.
3. Depois de `WiFi connected`, a placa mostra uma linha como esta:

```
Camera Ready! Use 'http://192.168.0.123' to connect
```

Esse é o IP da câmera. O computador precisa estar na **mesma rede Wi-Fi**.

## 4. Acessar a câmera

O firmware sobe dois servidores HTTP:

| Porta | Uso |
|-------|-----|
| **80** | Interface web, captura de foto e configuração |
| **81** | Stream de vídeo (MJPEG) |

### Endpoints principais

| URL | O que faz |
|-----|-----------|
| `http://<IP>/` | Interface web com sliders: resolução, qualidade, brilho, flash etc. |
| `http://<IP>/capture` | Tira **uma foto JPEG**. É o endpoint usado no pipeline do YOLO. |
| `http://<IP>:81/stream` | Vídeo ao vivo (MJPEG). Abra direto no navegador. |
| `http://<IP>/status` | JSON com a configuração atual do sensor. |
| `http://<IP>/control?var=<nome>&val=<valor>` | Altera um parâmetro. Exemplos: `var=quality&val=10`, `var=led_intensity&val=255`. |

Endpoints de debug: `/bmp`, `/xclk`, `/reg`, `/greg`, `/pll` e `/resolution`.

> Ajustes feitos pela interface ou pelo `/control` valem **só até a placa reiniciar**. Para deixá-los fixos, coloque-os no `setup()` do `CameraWebServer.ino`.

> O stream (porta 81) e o `/capture` disputam a câmera. Para capturar fotos pelo script, deixe o stream fechado.

## 5. Capturar fotos em Python

```python
import requests

IP = "192.168.0.123"  # IP mostrado no Serial Monitor

resp = requests.get(f"http://{IP}/capture", timeout=10)
resp.raise_for_status()
with open("foto.jpg", "wb") as f:
    f.write(resp.content)
```

A placa inicia com resolução **QVGA (320x240)**. Para ter fotos mais nítidas para o YOLO:

1. Aumente a resolução pela interface web, em `Resolution`.
2. Confira o valor de `framesize` em `/status`.
3. Fixe esse valor no `setup()`.

## Estrutura

| Arquivo | Conteúdo |
|---------|----------|
| `CameraWebServer.ino` | Setup da câmera e do Wi-Fi |
| `secrets.h` | Credenciais do Wi-Fi (fora do git) |
| `board_config.h` | Modelo da placa (`CAMERA_MODEL_AI_THINKER`) |
| `camera_pins.h` | Pinos de cada modelo de placa |
| `app_httpd.cpp` | Servidor HTTP e endpoints |
| `camera_index.h` | Página web (HTML compactado) |
| `partitions.csv` | Tabela de partições |
