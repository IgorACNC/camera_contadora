"""Cliente MQTT do dashboard: pede fotos à câmera e recebe as contagens do servico_contagem.py.

Quem conta os ovos é o applications/contador/servico_contagem.py. O dashboard só publica o pedido
e escuta o resultado em ovitrampa/cam1/contagem e o status do serviço em ovitrampa/servico/status.
"""

import json
import random
import threading
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from captura_mqtt import TOPICO_FOTO, TOPICO_PEDIDO

TOPICO_CONTAGEM = "ovitrampa/cam1/contagem"
TOPICO_STATUS_SERVICO = "ovitrampa/servico/status"


class ErroCaptura(Exception):
    pass


@dataclass
class EstadoConexao:
    conectado: bool = False
    erro: str | None = None
    ultima_foto: str | None = None  # ISO, última contagem recebida
    camera: str = "desconhecida"  # desconhecida | online | sem_resposta
    servico_online: bool = False  # status retido publicado pelo servico_contagem.py
    extras: dict = field(default_factory=dict)


class CameraMQTT:
    """Mantém uma conexão com o broker, pede fotos à ESP32-CAM e recebe as contagens."""

    simulada = False

    def __init__(self, host: str, port: int, ao_mudar, ao_resultado_externo):
        self.host, self.port = host, port
        self.estado = EstadoConexao(extras={"broker": f"{host}:{port}"})
        self._ao_mudar = ao_mudar  # chamado (de outra thread) quando o estado muda
        self._ao_resultado_externo = ao_resultado_externo  # contagem que chegou sem pedido do dashboard
        self._lock = threading.Lock()
        self._esperando: threading.Event | None = None
        self._resultado: dict | None = None

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
            client.subscribe([(TOPICO_CONTAGEM, 0), (TOPICO_STATUS_SERVICO, 0)])
            self.estado.conectado, self.estado.erro = True, None
        self._ao_mudar()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.estado.conectado = False
        self.estado.servico_online = False  # sem broker não dá para saber; o status retido volta ao reconectar
        self.estado.erro = None if reason_code == 0 else str(reason_code)
        self._ao_mudar()

    def _on_message(self, client, userdata, msg):
        if msg.topic == TOPICO_STATUS_SERVICO:
            self.estado.servico_online = msg.payload == b"online"
            self._ao_mudar()
            return

        # Tópico anônimo: só aceita JSON com "ovos" inteiro.
        try:
            dados = json.loads(msg.payload)
        except ValueError:
            return
        if not isinstance(dados, dict) or type(dados.get("ovos")) is not int:
            return

        with self._lock:
            self.estado.ultima_foto = datetime.now().isoformat(timespec="seconds")
            self.estado.camera = "online"
            pedido = self._esperando
            if pedido is not None:
                self._resultado = dados
                pedido.set()
        if pedido is None:
            self._ao_resultado_externo(dados)

    def _publicar_pedido(self):
        self._client.publish(TOPICO_PEDIDO, b"1")

    def capturar(self, timeout: float) -> dict:
        """Pede uma foto e devolve o JSON da contagem. Bloqueia: chamar fora do event loop (asyncio.to_thread)."""
        if not self.estado.conectado:
            raise ErroCaptura(f"Broker MQTT desconectado ({self.host}:{self.port})")
        if not self.estado.servico_online:
            raise ErroCaptura("Serviço de contagem offline — rode applications/contador/servico_contagem.py")
        evento = threading.Event()
        with self._lock:
            self._esperando, self._resultado = evento, None
        try:
            self._publicar_pedido()
            # A primeira contagem que chegar dentro do prazo é a resposta deste pedido.
            if not evento.wait(timeout):
                self.estado.camera = "sem_resposta"
                raise ErroCaptura(f"A câmera não respondeu em {timeout:.0f} s")
            with self._lock:
                return self._resultado
        finally:
            with self._lock:
                self._esperando = None


class CameraSimulada(CameraMQTT):
    """Sem câmera: em vez do pedido, publica uma foto de teste do dataset no tópico da foto.

    A contagem continua vindo do servico_contagem.py, igual ao fluxo real.
    """

    simulada = True

    def __init__(self, host: str, port: int, zip_dataset: Path, ao_mudar, ao_resultado_externo):
        super().__init__(host, port, ao_mudar, ao_resultado_externo)
        self._zip = zipfile.ZipFile(zip_dataset)
        self._imagens = [
            n for n in self._zip.namelist() if n.startswith("test/images/") and not n.endswith("/")
        ]
        if not self._imagens:
            raise ValueError(f"nenhuma imagem de teste em {zip_dataset}")
        self.estado.extras["fotos"] = len(self._imagens)

    def parar(self):
        super().parar()
        self._zip.close()

    def _publicar_pedido(self):
        self._client.publish(TOPICO_FOTO, self._zip.read(random.choice(self._imagens)))
