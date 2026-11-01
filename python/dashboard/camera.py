"""Fontes de foto: a ESP32-CAM via MQTT, ou fotos do dataset no modo simulação."""

import random
import threading
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from captura_mqtt import TOPICO_FOTO, TOPICO_PEDIDO


class ErroCaptura(Exception):
    pass


@dataclass
class Foto:
    dados: bytes
    # Só no modo simulação: caixas YOLO (cx, cy, w, h normalizados) do rótulo do dataset.
    rotulos: list[tuple[float, float, float, float]] | None = None


@dataclass
class EstadoConexao:
    conectado: bool = False
    erro: str | None = None
    ultima_foto: str | None = None  # ISO, última foto recebida da câmera
    camera: str = "desconhecida"  # desconhecida | online | sem_resposta
    extras: dict = field(default_factory=dict)


class CameraMQTT:
    """Mantém uma conexão com o broker e pede fotos à ESP32-CAM sob demanda."""

    simulada = False

    def __init__(self, host: str, port: int, ao_mudar):
        self.host, self.port = host, port
        self.estado = EstadoConexao(extras={"broker": f"{host}:{port}"})
        self._ao_mudar = ao_mudar  # chamado (de outra thread) quando o estado muda
        self._lock = threading.Lock()
        self._esperando: threading.Event | None = None
        self._foto: bytes | None = None

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=10)

    def iniciar(self):
        # connect_async + loop_start: tenta reconectar sozinho se o broker cair ou ainda não estiver no ar.
        self._client.connect_async(self.host, self.port)
        self._client.loop_start()

    def parar(self):
        self._client.loop_stop()
        self._client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.estado.conectado, self.estado.erro = False, str(reason_code)
        else:
            client.subscribe(TOPICO_FOTO)
            self.estado.conectado, self.estado.erro = True, None
        self._ao_mudar()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.estado.conectado = False
        self.estado.erro = None if reason_code == 0 else str(reason_code)
        self._ao_mudar()

    def _on_message(self, client, userdata, msg):
        with self._lock:
            self.estado.ultima_foto = datetime.now().isoformat(timespec="seconds")
            if self._esperando is not None:
                self._foto = msg.payload
                self._esperando.set()

    def capturar(self, timeout: float) -> Foto:
        """Bloqueia até a foto chegar. Chamar fora do event loop (asyncio.to_thread)."""
        if not self.estado.conectado:
            raise ErroCaptura(f"Broker MQTT desconectado ({self.host}:{self.port})")
        evento = threading.Event()
        with self._lock:
            self._esperando, self._foto = evento, None
        try:
            self._client.publish(TOPICO_PEDIDO, b"1")
            if not evento.wait(timeout):
                self.estado.camera = "sem_resposta"
                raise ErroCaptura(f"A câmera não respondeu em {timeout:.0f} s")
            with self._lock:
                dados = self._foto
        finally:
            with self._lock:
                self._esperando = None
        self.estado.camera = "online"
        return Foto(dados)


class CameraSimulada:
    """Devolve fotos aleatórias do split de teste do dataset, com um atraso parecido com o da ESP32."""

    simulada = True

    def __init__(self, zip_dataset: Path, ao_mudar):
        self._zip = zipfile.ZipFile(zip_dataset)
        self._imagens = [
            n for n in self._zip.namelist() if n.startswith("test/images/") and not n.endswith("/")
        ]
        if not self._imagens:
            raise ValueError(f"nenhuma imagem de teste em {zip_dataset}")
        self.estado = EstadoConexao(conectado=True, extras={"broker": "simulado", "fotos": len(self._imagens)})
        self._ao_mudar = ao_mudar

    def iniciar(self):
        self._ao_mudar()

    def parar(self):
        self._zip.close()

    def capturar(self, timeout: float) -> Foto:
        time.sleep(random.uniform(0.6, 1.6))
        nome = random.choice(self._imagens)
        dados = self._zip.read(nome)
        rotulo = "test/labels/" + Path(nome).stem + ".txt"
        texto = self._zip.read(rotulo).decode() if rotulo in self._zip.namelist() else ""
        rotulos = [tuple(map(float, l.split()[1:5])) for l in texto.splitlines() if l.strip()]
        self.estado.ultima_foto = datetime.now().isoformat(timespec="seconds")
        self.estado.camera = "online"
        return Foto(dados, rotulos)
