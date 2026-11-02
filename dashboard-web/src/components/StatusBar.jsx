import { fmtHora } from "../formato.js";

function Pill({ estado, rotulo, detalhe }) {
  return (
    <span className={`pill ${estado}`} title={detalhe}>
      <span className="ponto" />
      {rotulo}
    </span>
  );
}

export default function StatusBar({ conectado, status }) {
  if (!status) {
    return (
      <div className="pills">
        <Pill estado={conectado ? "ok" : "ruim"} rotulo={conectado ? "Servidor" : "Servidor offline"} />
      </div>
    );
  }
  const { mqtt, camera, servico } = status;

  const cam = {
    online: ["ok", "Câmera online"],
    sem_resposta: ["ruim", "Câmera sem resposta"],
    desconhecida: ["neutro", "Câmera: aguardando"],
  }[camera.estado] ?? ["neutro", camera.estado];

  return (
    <div className="pills">
      <Pill estado={conectado ? "ok" : "ruim"} rotulo={conectado ? "Servidor" : "Servidor offline"} />
      <Pill
        estado={mqtt.conectado ? "ok" : "ruim"}
        rotulo={mqtt.conectado ? "MQTT" : "MQTT offline"}
        detalhe={`Broker ${mqtt.broker}${mqtt.erro ? ` — ${mqtt.erro}` : ""}`}
      />
      <Pill estado={cam[0]} rotulo={cam[1]} detalhe={`Última foto: ${fmtHora(camera.ultima_foto)}`} />
      <Pill
        estado={servico.online ? "ok" : "ruim"}
        rotulo={servico.online ? "Contador online" : "Contador offline"}
        detalhe="applications/contador/servico_contagem.py"
      />
    </div>
  );
}
