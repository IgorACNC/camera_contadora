# camera_contadora — contagem de ovos de *Aedes aegypti* em ovitrampas

Sistema IoT que fotografa ovitrampas com uma **ESP32-CAM** e conta os ovos de *Aedes aegypti* com um modelo **YOLO**. As fotos chegam ao PC via **MQTT**, e um script Python pede a foto, recebe a imagem e roda a contagem.

Projeto da disciplina **Sistemas Embarcados** (CESAR School).

## Arquitetura

```
┌──────────────┐  ovitrampa/cam1/capturar   ┌───────────────────┐
│              │ ◄───────────────────────── │                   │
│  ESP32-CAM   │                            │  Mosquitto (PC)   │ ◄──► Python
│  (OV2640)    │ ─────────────────────────► │  porta 1883       │      captura_mqtt.py
│              │  ovitrampa/cam1/foto (JPEG)│                   │      contar_ovos.py (YOLO)
└──────────────┘                            └───────────────────┘
```

1. O script Python publica um pedido em `ovitrampa/cam1/capturar`.
2. A ESP32-CAM tira uma foto SVGA (800x600) e publica o JPEG em `ovitrampa/cam1/foto`.
3. O script salva a foto em `capturas/`.
4. O modelo YOLO conta os ovos da foto.

## Firmware da câmera (outro repositório)

O firmware da ESP32-CAM fica em **https://github.com/IgorACNC/esp32-camera-contadora** e está incluído aqui como **submódulo**, na pasta `esp32-camera-contadora/`.

As instruções de compilar e gravar (PlatformIO), a configuração do `secrets.h` e a arquitetura FreeRTOS estão no README de lá.

**Clonar este repositório junto com o submódulo:**

```sh
git clone --recurse-submodules https://github.com/IgorACNC/camera_contadora.git
```

Se você já clonou sem o submódulo:

```sh
git submodule update --init
```

**Atualizar o ponteiro do submódulo** depois de novos commits no repo da câmera:

```sh
git submodule update --remote esp32-camera-contadora
git add esp32-camera-contadora
git commit -m "Atualiza firmware da câmera"
git push
```

## MQTT

| Tópico | Direção | Conteúdo |
|--------|---------|----------|
| `ovitrampa/cam1/capturar` | PC → câmera | Pedido de foto (qualquer payload) |
| `ovitrampa/cam1/foto` | câmera → PC | JPEG binário |

- **Broker:** Mosquitto no PC. Ele precisa aceitar conexões da rede local:
  ```
  listener 1883
  allow_anonymous true
  ```
- **Rede:** a ESP32-CAM e o PC precisam estar na **mesma rede Wi-Fi**, e ela precisa ser de 2.4 GHz.
- **Firewall:** se a câmera não conectar (`state=-2` no Serial), libere a porta 1883 de entrada no firewall do Windows.

## Capturar uma foto em Python

**1. Criar o ambiente** (uma vez só, na raiz do projeto):

```powershell
python -m venv python/.venv
python/.venv/Scripts/python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
python/.venv/Scripts/python.exe -m pip install -r python/requirements-treino.txt
```

O PyTorch com CUDA é instalado à parte, na primeira linha de instalação. O `requirements-treino.txt` traz a `ultralytics` e o `paho-mqtt`.

**2. Pedir uma foto:**

```powershell
python/.venv/Scripts/python.exe python/captura_mqtt.py
```

- Por padrão, o script usa o broker em `localhost`. Use `--host <IP>` se o broker estiver em outra máquina.
- A foto é salva em `capturas/foto_AAAAMMDD_HHMMSS.jpg`.
- Se nenhuma foto chegar em 15 s, o script mostra uma mensagem de timeout.

**Alternativa via HTTP:** o firmware também serve `http://<IP da câmera>/capture`, que devolve uma foto JPEG direto no navegador. O IP aparece no Serial Monitor da câmera.

## Modelo YOLO (contagem)

- **Modelo:** **YOLO26s**, com uma única classe, **"ovo"**. As classes originais aegypti e albopictus foram unidas.
- **`max_det`:** a validação e a predição usam sempre `max_det=1000`, porque há imagens com mais de 500 ovos e o padrão de 300 cortaria a contagem.

Todos os comandos rodam a partir da raiz, com `python/.venv/Scripts/python.exe`:

| Script | O que faz |
|--------|-----------|
| `python/treino/preparar_dataset.py` | Extrai o zip do dataset e gera `python/datasets/ovos/` com a classe única e o `data.yaml`. Também tira do treino as imagens que vêm da mesma foto original de uma imagem de validação ou teste. |
| `python/treino/treinar.py` | Treina o YOLO26s (150 épocas, patience 30). Opções: `--batch` (padrão 8), `--workers` (padrão 2) e `--retomar <last.pt>`, que continua um treino interrompido, inclusive em outra máquina. |
| `python/treino/avaliar_contagem.py` | Imprime mAP50, mAP50-95, precisão e recall no teste. Escolhe na validação o limiar de confiança de menor erro de contagem (MAE) e mede o MAE no teste. Salva o limiar em `weights/conf_contagem.txt`. |
| `python/contar_ovos.py <imagens...>` | Mostra "N ovos" por imagem e salva as imagens anotadas em `capturas/anotadas/`. Opções: `--modelo` e `--conf`. |

Os pesos ficam em `python/runs/<treino>/weights/best.pt`, fora do git.

## Dataset e licença

Dataset **Roboflow "aedes eggs v6"** (mosquito-eggs / aedes-eggs-mntab, versão 6), licença **CC BY 4.0**, com atribuição obrigatória:
https://universe.roboflow.com/mosquito-eggs/aedes-eggs-mntab/dataset/6

## Estrutura de pastas

| Caminho | Conteúdo |
|---------|----------|
| `esp32-camera-contadora/` | Submódulo com o firmware da ESP32-CAM (PlatformIO + FreeRTOS) |
| `python/` | Scripts de captura (`captura_mqtt.py`), contagem (`contar_ovos.py`) e treino (`treino/`), além do zip do dataset |
| `capturas/` | Fotos capturadas e anotadas (fora do git) |
| `Projeto-Embarcados_CesarSchool-CSBC.pdf` | Enunciado da disciplina |
