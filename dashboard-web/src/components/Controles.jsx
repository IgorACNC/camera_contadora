import { useEffect, useState } from "react";
import { fmtContagem } from "../formato.js";

export default function Controles({ status, conectado, capturar, salvarConfig }) {
  const [erro, setErro] = useState(null);
  const [intervalo, setIntervalo] = useState("");
  const [agora, setAgora] = useState(Date.now());

  const config = status?.config;
  useEffect(() => {
    if (config) setIntervalo(String(config.intervalo_min));
  }, [config?.intervalo_min]);

  useEffect(() => {
    const t = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const ocupado = !!status?.ocupado;
  const desabilitado = !conectado || !status;

  async function tentar(fn) {
    setErro(null);
    try {
      await fn();
    } catch (e) {
      setErro(e.message);
    }
  }

  function salvarIntervalo() {
    const v = parseFloat(intervalo.replace(",", "."));
    if (!Number.isFinite(v) || v < 0.5) {
      setErro("Intervalo mínimo: 0,5 min");
      setIntervalo(String(config.intervalo_min));
      return;
    }
    if (v !== config.intervalo_min) tentar(() => salvarConfig({ intervalo_min: v }));
  }

  const faltam = status?.proxima_auto ? (new Date(status.proxima_auto).getTime() - agora) / 1000 : null;

  return (
    <section className="card">
      <h2>Controles</h2>
      <button className="botao-principal" disabled={desabilitado || ocupado} onClick={() => tentar(capturar)}>
        {ocupado ? "Capturando…" : "Capturar agora"}
      </button>

      <div className="linha-config">
        <label className="interruptor">
          <input
            type="checkbox"
            checked={!!config?.auto_ativo}
            disabled={desabilitado}
            onChange={(e) => tentar(() => salvarConfig({ auto_ativo: e.target.checked }))}
          />
          <span>Captura automática</span>
        </label>
        <span className="contagem-auto">
          {config?.auto_ativo ? (ocupado ? "capturando…" : `próxima em ${fmtContagem(faltam)}`) : "desligada"}
        </span>
      </div>

      <label className="campo">
        <span>Intervalo (minutos)</span>
        <input
          type="number"
          min="0.5"
          step="0.5"
          value={intervalo}
          disabled={desabilitado}
          onChange={(e) => setIntervalo(e.target.value)}
          onBlur={salvarIntervalo}
          onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
        />
      </label>

      {config && (
        <label className="campo">
          <span>
            Limiar de confiança: <strong>{config.conf_efetivo.toFixed(2)}</strong>
            {config.conf == null ? " (padrão da avaliação)" : ""}
          </span>
          <div className="slider-linha">
            <input
              type="range"
              min="0.05"
              max="0.95"
              step="0.05"
              value={config.conf_efetivo}
              disabled={desabilitado}
              onChange={(e) => tentar(() => salvarConfig({ conf: parseFloat(e.target.value) }))}
            />
            {config.conf != null && (
              <button className="link" onClick={() => tentar(() => salvarConfig({ conf: null }))}>
                padrão
              </button>
            )}
          </div>
        </label>
      )}

      {erro && <p className="msg-erro">{erro}</p>}
    </section>
  );
}
