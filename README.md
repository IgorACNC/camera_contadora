# camera_contadora — contagem de ovos de *Aedes aegypti* em ovitrampas

Sistema IoT que fotografa ovitrampas com uma **ESP32-CAM** e conta os ovos de *Aedes aegypti* com um modelo **YOLO**. As fotos chegam ao PC via **MQTT**, e um script Python pede a foto, recebe a imagem e roda a contagem.

Projeto da disciplina **Sistemas Embarcados** (CESAR School).

## Arquitetura

```
ESP32-CAM ◄── ovitrampa/cam1/capturar ──── dashboard / captura_mqtt.py
    │
    └──────── ovitrampa/cam1/foto (JPEG) ──► servico_contagem.py (YOLO26s)
                                                   │
dashboard ◄── ovitrampa/cam1/contagem (JSON) ──────┘
dashboard ◄── ovitrampa/servico/status (online/offline, retido)

Todas as mensagens passam pelo Mosquitto no PC (porta 1883).
```

1. O dashboard (ou o `captura_mqtt.py`) publica um pedido em `ovitrampa/cam1/capturar`.
2. A ESP32-CAM tira uma foto SVGA (800x600) e publica o JPEG em `ovitrampa/cam1/foto`.
3. O `servico_contagem.py` recebe a foto, roda o YOLO e salva a original e a anotada em `capturas/`.
4. O serviço publica o resultado em JSON em `ovitrampa/cam1/contagem`, e o dashboard mostra.

## Como rodar tudo

Passo a passo do zero até o dashboard contando ovos. Os comandos rodam no PowerShell, a partir da raiz do repositório.

### 0. Pré-requisitos

| O quê | Para quê |
|-------|----------|
| Python 3.13 | serviço de contagem e backend do dashboard |
| Node.js 20+ | compilar o frontend do dashboard |
| [Mosquitto](https://mosquitto.org/download/) | broker MQTT no PC |
| VS Code + PlatformIO | só para gravar o firmware na câmera |
| GPU NVIDIA (opcional) | acelera o YOLO; sem ela roda na CPU, mais devagar |

### 1. Clonar com o submódulo do firmware

```powershell
git clone --recurse-submodules https://github.com/IgorACNC/camera_contadora.git
cd camera_contadora
```

### 2. Instalar (uma vez só)

```powershell
python -m venv python/.venv
python/.venv/Scripts/python.exe -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
python/.venv/Scripts/python.exe -m pip install -r python/requirements-treino.txt -r python/requirements-dashboard.txt
cd dashboard-web; npm install; npm run build; cd ..
Copy-Item .env.example .env   # depois preencha o SMTP e os destinatários do relatório
```

O modelo treinado já vem no repositório: `python/runs/ovos_yolo26s-2/weights/best.pt`, com o limiar em `conf_contagem.txt`. Não é preciso treinar.

### 3. Configurar o Mosquitto

No `mosquitto.conf`, deixe:

```
listener 1883
allow_anonymous true
```

Reinicie o serviço do Mosquitto. Se a câmera não conectar, veja [MQTT](#mqtt): firewall e rede privada.

### 4. Gravar a câmera (só com a ESP32-CAM)

1. Descubra o IP do PC na rede Wi-Fi com `ipconfig` (campo "Endereço IPv4" do adaptador Wi-Fi).
2. No submódulo `esp32-camera-contadora/`, copie `include/secrets.example.h` para `include/secrets.h` e preencha `WIFI_SSID`, `WIFI_PASSWORD` e `MQTT_HOST` (o IP do passo 1). A rede precisa ser de 2.4 GHz.
3. Grave com o PlatformIO, como explicado no README do submódulo. O Serial deve mostrar `MQTT conectado`.

> Se o IP do PC mudar (DHCP), a câmera mostra `MQTT falhou, state=-2`. Atualize o `MQTT_HOST` ou reserve o IP no roteador.

Sem câmera? Pule este passo e use o `--simular` no passo 5.

### 5. Rodar

```powershell
# Terminal 1 — serviço de contagem (obrigatório, deixe aberto)
python/.venv/Scripts/python.exe applications/contador/servico_contagem.py

# Terminal 2 — dashboard
python/.venv/Scripts/python.exe python/servidor_dashboard.py              # com a câmera
python/.venv/Scripts/python.exe python/servidor_dashboard.py --simular    # sem câmera (fotos do dataset)
```

Abra **http://localhost:8000** e clique em **Capturar agora**.

### 6. Conferir que funcionou

- A pílula do dashboard mostra **Contador online**.
- Ao capturar, as etapas vão de pedido → contando → pronto, e aparecem a contagem e a foto anotada.
- O Terminal 1 mostra a mesma contagem.
- As fotos ficam em `capturas/`, e as anotadas em `capturas/anotadas/`.

Mais detalhes: [Dashboard](#dashboard-tempo-real) · [Serviço de contagem](applications/contador/README.md) · [Modelo YOLO](#modelo-yolo-contagem).

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
| `ovitrampa/cam1/contagem` | serviço → dashboard | Resultado da contagem em JSON (ver `applications/contador/README.md`) |
| `ovitrampa/servico/status` | serviço → dashboard | `online` / `offline`, retido (Last Will) |

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

## Dashboard (tempo real)

Página web que dispara as capturas e mostra as métricas ao vivo: contagem e foto anotada, etapas da captura (pedido → contando → pronto), status do MQTT, da câmera e do contador, tempos de captura e inferência, gráficos e histórico.

- **Contador:** o dashboard **não roda o YOLO**. Quem conta é o `applications/contador/servico_contagem.py`, que **precisa estar rodando**. O dashboard só pede a foto e recebe o JSON em `ovitrampa/cam1/contagem`. A pílula "Contador online/offline" vem do tópico `ovitrampa/servico/status`.
- **Backend:** `python/servidor_dashboard.py` (FastAPI). Mantém a conexão MQTT aberta e manda eventos ao navegador por WebSocket. O histórico fica em `capturas/dashboard.db` (SQLite).
- **Frontend:** `dashboard-web/` (React + Vite + Recharts).
- **Disparo:** botão "Capturar agora" e captura automática a cada N minutos, configurável na própria página. O limiar de confiança é o do serviço e só é exibido.
- **Origem "externa":** toda contagem publicada pelo serviço entra no histórico. As que não foram pedidas pelo dashboard (por exemplo, uma foto pedida pelo `captura_mqtt.py` ou enviada pelo `enviar_imagem.py`) aparecem com origem **externa**.

**Instalar (uma vez só):**

```powershell
python/.venv/Scripts/python.exe -m pip install -r python/requirements-dashboard.txt
cd dashboard-web; npm install; npm run build; cd ..
```

**Rodar** (da raiz do projeto):

```
# Terminal 1 — contador (obrigatório)
python\.venv\Scripts\python.exe applications\contador\servico_contagem.py
# Terminal 2 — dashboard (abrir http://localhost:8000)
python\.venv\Scripts\python.exe python\servidor_dashboard.py            # com a câmera
python\.venv\Scripts\python.exe python\servidor_dashboard.py --simular  # sem câmera
```

Abra **http://localhost:8000**. Opções:

| Opção | O que faz |
|-------|-----------|
| `--mqtt-host <IP>` / `--mqtt-port` | Broker MQTT (padrão `localhost:1883`) |
| `--simular` | Sem câmera: em vez de pedir à câmera, publica uma foto de teste do dataset em `ovitrampa/cam1/foto`. Precisa do `servico_contagem.py` rodando, que conta igual ao fluxo real |
| `--host 0.0.0.0` | Deixa abrir o dashboard de outro computador ou celular na mesma rede |

### Enviar relatório PDF por e-mail

No fim da página do dashboard, escolha um dos destinatários autorizados e clique em **Gerar e enviar PDF**. O anexo contém um resumo das capturas e uma tabela com até 5.000 registros do histórico SQLite.

A configuração fica no arquivo `.env` da raiz, que está fora do git porque tem senha. Copie o `.env.example` para `.env` e preencha (no Gmail, use uma senha de app, não a senha normal da conta):

```ini
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu.email@gmail.com
SMTP_PASSWORD=sua-senha-de-app
SMTP_FROM=
RELATORIO_DESTINOS=pessoa1@exemplo.com,pessoa2@exemplo.com
```

- **Destinatários:** a página só envia para os e-mails de `RELATORIO_DESTINOS`, separados por vírgula. Qualquer outro endereço é recusado (403). Sem nenhum, o envio fica desativado.
- **Mudanças:** o `.env` é lido ao iniciar o servidor. Para mudar a lista ou o SMTP, reinicie o `servidor_dashboard.py`.
- **Limite:** 1 envio por minuto no servidor todo.
- **`$env:` no terminal:** continua funcionando e tem prioridade sobre o `.env`.
- **Outros provedores:** use o host e a porta SMTP com STARTTLS do provedor. `SMTP_FROM` pode ficar vazio se o remetente for o `SMTP_USER`. Sem SMTP configurado, a página avisa e desabilita o botão.


**Desenvolvendo o frontend:** com o backend rodando, `cd dashboard-web; npm run dev` abre em http://localhost:5173 com recarga automática. API e WebSocket são repassados para a porta 8000.

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

O modelo final (`python/runs/ovos_yolo26s-2/weights/best.pt` + `conf_contagem.txt`) está versionado. O `last.pt` e os demais pesos ficam fora do git.

## Dataset e licença

Dataset **Roboflow "aedes eggs v6"** (mosquito-eggs / aedes-eggs-mntab, versão 6), licença **CC BY 4.0**, com atribuição obrigatória:
https://universe.roboflow.com/mosquito-eggs/aedes-eggs-mntab/dataset/6

## Estrutura de pastas

| Caminho | Conteúdo |
|---------|----------|
| `esp32-camera-contadora/` | Submódulo com o firmware da ESP32-CAM (PlatformIO + FreeRTOS) |
| `python/` | Scripts de captura (`captura_mqtt.py`), contagem (`contar_ovos.py`) e treino (`treino/`), além do zip do dataset |
| `applications/contador/` | Serviço de contagem via MQTT (`servico_contagem.py`) e script de teste (`enviar_imagem.py`) |
| `python/dashboard/` | Backend do dashboard (API, WebSocket, cliente MQTT, SQLite) |
| `dashboard-web/` | Frontend React do dashboard |
| `capturas/` | Fotos capturadas e anotadas (fora do git) |
| `Projeto-Embarcados_CesarSchool-CSBC.pdf` | Enunciado da disciplina |
