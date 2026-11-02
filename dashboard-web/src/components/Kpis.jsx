import { fmtMs, fmtPct } from "../formato.js";

function Kpi({ rotulo, valor, detalhe, destaque }) {
  return (
    <div className={`kpi ${destaque ? "destaque" : ""}`}>
      <span className="kpi-rotulo">{rotulo}</span>
      <span className="kpi-valor">{valor}</span>
      {detalhe && <span className="kpi-detalhe">{detalhe}</span>}
    </div>
  );
}

const media = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null);

export default function Kpis({ capturas }) {
  const ok = capturas.filter((c) => c.status === "ok");
  const ultima = ok.at(-1);
  const anterior = ok.at(-2);
  const ultimas10 = ok.slice(-10);
  const hoje = new Date().toDateString();
  const deHoje = capturas.filter((c) => new Date(c.inicio).toDateString() === hoje);
  const errosHoje = deHoje.filter((c) => c.status === "erro").length;

  let variacao = null;
  if (ultima && anterior) {
    const d = ultima.ovos - anterior.ovos;
    variacao = `${d > 0 ? "+" : ""}${d} vs. anterior`;
  }
  const mediaOvos = media(ultimas10.map((c) => c.ovos));

  return (
    <section className="kpis">
      <Kpi destaque rotulo="Ovos na última captura" valor={ultima ? ultima.ovos : "—"} detalhe={variacao} />
      <Kpi
        rotulo="Média (últimas 10)"
        valor={mediaOvos == null ? "—" : mediaOvos.toFixed(1)}
        detalhe={ultimas10.length ? `máx. ${Math.max(...ultimas10.map((c) => c.ovos))}` : null}
      />
      <Kpi
        rotulo="Capturas hoje"
        valor={deHoje.length}
        detalhe={errosHoje ? `${errosHoje} com erro` : "nenhum erro"}
      />
      <Kpi
        rotulo="Tempo de captura"
        valor={fmtMs(ultima?.tempo_captura_ms)}
        detalhe={`média ${fmtMs(media(ultimas10.map((c) => c.tempo_captura_ms)))}`}
      />
      <Kpi
        rotulo="Tempo de inferência"
        valor={fmtMs(ultima?.tempo_inferencia_ms)}
        detalhe={`média ${fmtMs(media(ultimas10.map((c) => c.tempo_inferencia_ms)))}`}
      />
      <Kpi
        rotulo="Confiança média"
        valor={fmtPct(ultima?.conf_media)}
        detalhe="das detecções"
      />
    </section>
  );
}
