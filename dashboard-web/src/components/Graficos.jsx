import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fmtDataHora, fmtHora } from "../formato.js";

const COR_OVOS = "var(--serie-1)";
const COR_CAPTURA = "var(--serie-2)";
const COR_INFERENCIA = "var(--serie-3)";

const eixo = { stroke: "var(--texto-fraco)", fontSize: 12, tickLine: false };

export default function Graficos({ capturas }) {
  const ok = capturas.filter((c) => c.status === "ok");
  const dados = ok.map((c) => ({
    id: c.id,
    hora: c.inicio,
    ovos: c.ovos,
    captura: c.tempo_captura_ms != null ? c.tempo_captura_ms / 1000 : null,
    inferencia: c.tempo_inferencia_ms != null ? c.tempo_inferencia_ms / 1000 : null,
  }));

  if (!dados.length) {
    return (
      <section className="card">
        <h2>Ovos ao longo do tempo</h2>
        <p className="vazio">O gráfico aparece depois da primeira captura com sucesso.</p>
      </section>
    );
  }

  const tooltip = {
    contentStyle: { background: "var(--card)", border: "1px solid var(--borda)", borderRadius: 8 },
    labelFormatter: (_, p) => (p?.[0] ? `#${p[0].payload.id} · ${fmtDataHora(p[0].payload.hora)}` : ""),
  };

  return (
    <div className="graficos">
      <section className="card">
        <h2>Ovos ao longo do tempo</h2>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={dados} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="var(--grade)" vertical={false} />
            <XAxis dataKey="hora" tickFormatter={fmtHora} minTickGap={40} {...eixo} />
            <YAxis allowDecimals={false} {...eixo} />
            <Tooltip {...tooltip} formatter={(v) => [`${v} ovos`, "Contagem"]} />
            <Line type="linear" dataKey="ovos" stroke={COR_OVOS} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
      <section className="card">
        <h2>Tempos por captura</h2>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={dados} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
            <CartesianGrid stroke="var(--grade)" vertical={false} />
            <XAxis dataKey="hora" tickFormatter={fmtHora} minTickGap={40} {...eixo} />
            <YAxis unit=" s" {...eixo} />
            <Tooltip {...tooltip} formatter={(v, nome) => [`${v.toFixed(2)} s`, nome]} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line name="Captura (câmera)" type="monotone" dataKey="captura" stroke={COR_CAPTURA} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line name="Inferência (YOLO)" type="monotone" dataKey="inferencia" stroke={COR_INFERENCIA} strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}
