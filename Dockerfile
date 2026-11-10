# Imagens do camera_contadora. Um Dockerfile, dois alvos:
#   docker build --target contador  -t camera-contadora/contador .
#   docker build --target dashboard -t camera-contadora/dashboard .
# Normalmente tudo sobe junto com `docker compose up --build` (ver docker-compose.yml).

# ---------- frontend do dashboard (React + Vite) ----------
FROM node:22-slim AS front
WORKDIR /front
COPY dashboard-web/package.json dashboard-web/package-lock.json ./
RUN npm ci
COPY dashboard-web/ ./
RUN npm run build

# ---------- base Python comum ----------
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# ---------- serviço de contagem (YOLO) ----------
FROM base AS contador
# Bibliotecas de sistema que o OpenCV (via ultralytics) precisa.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# PyTorch vem à parte. Padrão: CPU. Para GPU NVIDIA, use
#   --build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN pip install torch torchvision --index-url ${TORCH_INDEX_URL}
COPY python/requirements-treino.txt python/
RUN pip install -r python/requirements-treino.txt
COPY python/rastreio_mlflow.py python/
COPY python/runs/ovos_yolo26s-2/weights/ python/runs/ovos_yolo26s-2/weights/
COPY applications/contador/ applications/contador/
# Pasta de config do Ultralytics gravável (evita o aviso de /root/.config).
ENV YOLO_CONFIG_DIR=/app/.config
RUN mkdir -p /app/.config/Ultralytics
# Fuso horário (horários das capturas e "capturas hoje"); TZ vem do compose.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
# O serviço trata Ctrl+C (SIGINT) publicando "offline" antes de sair.
STOPSIGNAL SIGINT
ENTRYPOINT ["python", "applications/contador/servico_contagem.py"]
CMD ["--host", "mosquitto"]

# ---------- dashboard (FastAPI + frontend compilado) ----------
FROM base AS dashboard
# Fuso horário (horários das capturas e "capturas hoje"); TZ vem do compose.
RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/*
COPY python/requirements-dashboard.txt python/
RUN pip install -r python/requirements-dashboard.txt paho-mqtt==2.1.0
COPY python/captura_mqtt.py python/servidor_dashboard.py python/
COPY python/dashboard/ python/dashboard/
# Dataset zipado: usado só pelo modo --simular (fotos de teste).
COPY ["python/aedes eggs.v6i.yolov8.zip", "python/"]
COPY --from=front /front/dist dashboard-web/dist
EXPOSE 8000
ENTRYPOINT ["python", "python/servidor_dashboard.py", "--host", "0.0.0.0"]
CMD ["--mqtt-host", "mosquitto"]
