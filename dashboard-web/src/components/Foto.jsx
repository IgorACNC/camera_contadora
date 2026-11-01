import { useState } from "react";
import { fmtDataHora } from "../formato.js";

export default function Foto({ captura, fixada, voltar }) {
  const [anotada, setAnotada] = useState(true);

  if (!captura) {
    return (
      <section className="card foto-card">
        <h2>Foto</h2>
        <div className="foto-vazia">Nenhuma foto ainda. Clique em “Capturar agora”.</div>
      </section>
    );
  }

  const temAnotada = !!captura.foto_anotada;
  const mostrarAnotada = anotada && temAnotada;
  const src = `/fotos/${mostrarAnotada ? "anotada" : "original"}/${mostrarAnotada ? captura.foto_anotada : captura.foto}`;

  return (
    <section className="card foto-card">
      <div className="foto-topo">
        <h2>
          {fixada ? "Captura" : "Última captura"} #{captura.id}
          <span className="etiqueta">{fmtDataHora(captura.inicio)}</span>
        </h2>
        <div className="foto-acoes">
          {fixada && (
            <button className="link" onClick={voltar}>
              voltar à mais recente
            </button>
          )}
          <div className="alternador">
            <button className={mostrarAnotada ? "sel" : ""} disabled={!temAnotada} onClick={() => setAnotada(true)}>
              Anotada
            </button>
            <button className={!mostrarAnotada ? "sel" : ""} onClick={() => setAnotada(false)}>
              Original
            </button>
          </div>
        </div>
      </div>
      <div className="foto-moldura">
        <img src={src} alt={`Captura ${captura.id}`} />
        {captura.status === "ok" && <span className="foto-contagem">{captura.ovos} ovos</span>}
      </div>
      {captura.status === "erro" && <p className="msg-erro">Erro na contagem: {captura.erro}</p>}
    </section>
  );
}
