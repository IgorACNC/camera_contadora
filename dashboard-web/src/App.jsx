import { useEffect, useMemo, useState } from "react";
import { useDashboard } from "./useDashboard.js";
import StatusBar from "./components/StatusBar.jsx";
import Kpis from "./components/Kpis.jsx";
import Controles from "./components/Controles.jsx";
import Etapas from "./components/Etapas.jsx";
import Foto from "./components/Foto.jsx";
import Graficos from "./components/Graficos.jsx";
import Historico from "./components/Historico.jsx";
import Relatorio from "./components/Relatorio.jsx";

export default function App() {
  const { conectado, status, capturas, etapas, capturar, salvarConfig } = useDashboard();
  const [selecionada, setSelecionada] = useState(null); // id escolhido na tabela; null = a mais recente

  const ultimaComFoto = useMemo(() => [...capturas].reverse().find((c) => c.foto), [capturas]);
  const fotoMostrada = capturas.find((c) => c.id === selecionada) ?? ultimaComFoto;

  // Quando chega uma captura nova, volta a mostrar a mais recente.
  useEffect(() => setSelecionada(null), [ultimaComFoto?.id]);

  return (
    <div className="pagina">
      <header className="topo">
        <div>
          <h1>Contador de ovos</h1>
          <p className="sub">Ovitrampa cam1 · ESP32-CAM + YOLO</p>
        </div>
        <StatusBar conectado={conectado} status={status} />
      </header>

      {status?.simulacao && (
        <div className="aviso">Modo simulação: as fotos vêm do conjunto de teste do dataset, não da câmera.</div>
      )}
      {status && !status.servico.online && (
        <div className="aviso erro">
          Serviço de contagem offline — rode applications/contador/servico_contagem.py
        </div>
      )}

      <Kpis capturas={capturas} />

      <div className="grade">
        <div className="coluna">
          <Controles status={status} conectado={conectado} capturar={capturar} salvarConfig={salvarConfig} />
          <Etapas etapas={etapas} ocupado={status?.ocupado} />
        </div>
        <Foto captura={fotoMostrada} fixada={selecionada != null} voltar={() => setSelecionada(null)} />
      </div>

      <Graficos capturas={capturas} />
      <Relatorio />
      <Historico capturas={capturas} selecionada={fotoMostrada?.id} selecionar={setSelecionada} />
    </div>
  );
}
