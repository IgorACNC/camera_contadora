import { useCallback, useEffect, useRef, useState } from "react";

const MAX_HISTORICO = 500;

function urlWebSocket() {
  const protocolo = location.protocol === "https:" ? "wss" : "ws";
  return `${protocolo}://${location.host}/ws`;
}

/**
 * Conecta no WebSocket do backend e mantém o estado do dashboard:
 * status do sistema, histórico de capturas e as etapas da captura em andamento.
 */
export function useDashboard() {
  const [conectado, setConectado] = useState(false);
  const [status, setStatus] = useState(null);
  const [capturas, setCapturas] = useState([]);
  const [etapas, setEtapas] = useState(null); // { id, origem, passos: {pedido: {...}, ...}, erro }
  const wsRef = useRef(null);

  useEffect(() => {
    let fechado = false;
    let timer;

    function conectar() {
      const ws = new WebSocket(urlWebSocket());
      wsRef.current = ws;
      ws.onopen = () => setConectado(true);
      ws.onclose = () => {
        setConectado(false);
        if (!fechado) timer = setTimeout(conectar, 2000);
      };
      ws.onmessage = (ev) => tratar(JSON.parse(ev.data));
    }

    function tratar(msg) {
      switch (msg.tipo) {
        case "status":
          setStatus(msg);
          // Página aberta no meio de uma captura: mostra pelo menos a etapa atual.
          if (msg.etapa) {
            setEtapas(
              (atual) =>
                atual ?? {
                  id: msg.etapa.id,
                  origem: msg.etapa.origem,
                  passos: { [msg.etapa.etapa]: msg.etapa },
                  erro: msg.etapa.erro ?? null,
                },
            );
          }
          break;
        case "historico":
          setCapturas(msg.capturas);
          break;
        case "captura":
          setCapturas((lista) => {
            const semEsta = lista.filter((c) => c.id !== msg.captura.id);
            return [...semEsta, msg.captura].sort((a, b) => a.id - b.id).slice(-MAX_HISTORICO);
          });
          break;
        case "etapa":
          setEtapas((atual) => {
            const base =
              atual && atual.id === msg.id ? atual : { id: msg.id, origem: msg.origem, passos: {}, erro: null };
            return {
              ...base,
              origem: base.origem ?? msg.origem,
              passos: { ...base.passos, [msg.etapa]: msg },
              erro: msg.etapa === "erro" ? msg.erro : base.erro,
            };
          });
          break;
      }
    }

    conectar();
    return () => {
      fechado = true;
      clearTimeout(timer);
      wsRef.current?.close();
    };
  }, []);

  const capturar = useCallback(async () => {
    const r = await fetch("/api/capturar", { method: "POST" });
    if (!r.ok) throw new Error((await r.json()).detail ?? `HTTP ${r.status}`);
  }, []);

  const salvarConfig = useCallback(async (config) => {
    const r = await fetch("/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(config),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  }, []);

  return { conectado, status, capturas, etapas, capturar, salvarConfig };
}
