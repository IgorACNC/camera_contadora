import { useEffect, useState } from "react";
import { fmtMs } from "../formato.js";

const PASSOS = [
  { id: "pedido", nome: "Pedido enviado", desc: "MQTT → câmera" },
  { id: "contando", nome: "Contando ovos", desc: "foto da câmera + YOLO no serviço" },
  { id: "pronto", nome: "Pronto", desc: "resultado salvo" },
];

export default function Etapas({ etapas, ocupado }) {
  const [agora, setAgora] = useState(Date.now());
  useEffect(() => {
    if (!ocupado) return;
    const t = setInterval(() => setAgora(Date.now()), 100);
    return () => clearInterval(t);
  }, [ocupado]);

  if (!etapas) {
    return (
      <section className="card">
        <h2>Etapas ao vivo</h2>
        <p className="vazio">Nenhuma captura desde que a página abriu.</p>
      </section>
    );
  }

  const { passos, erro, origem, id } = etapas;
  const t0 = passos.pedido ? new Date(passos.pedido.em).getTime() : null;
  const indiceErro = erro ? PASSOS.findIndex((p) => !passos[p.id]) : -1;
  const fim = passos.pronto ?? passos.erro;
  const decorrido = t0 == null ? null : (fim ? new Date(fim.em).getTime() : agora) - t0;

  return (
    <section className="card">
      <h2>
        Etapas ao vivo <span className="etiqueta">#{id} · {origem === "auto" ? "automática" : "manual"}</span>
      </h2>
      <ol className="etapas">
        {PASSOS.map((p, i) => {
          const feito = passos[p.id];
          const falhou = i === indiceErro;
          const ativo = !feito && !falhou && !erro && PASSOS.slice(0, i).every((q) => passos[q.id]);
          const classe = falhou ? "falhou" : feito ? "feito" : ativo ? "ativo" : "";
          const partes = [];
          if (feito && t0 != null) partes.push(`+${fmtMs(new Date(feito.em).getTime() - t0)}`);
          if (p.id === "pronto" && feito) partes.push(`${feito.ovos} ovos`);
          const extra = partes.length ? partes.join(" · ") : null;
          return (
            <li key={p.id} className={classe}>
              <span className="marcador">{falhou ? "!" : feito ? "✓" : i + 1}</span>
              <div>
                <strong>{p.nome}</strong>
                <span className="desc">{falhou ? erro : extra ?? p.desc}</span>
              </div>
            </li>
          );
        })}
      </ol>
      <p className="decorrido">
        {fim ? "Duração total" : "Decorrido"}: <strong>{fmtMs(decorrido)}</strong>
      </p>
    </section>
  );
}
