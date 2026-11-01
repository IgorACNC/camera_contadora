import { fmtBytes, fmtDataHora, fmtMs, fmtPct } from "../formato.js";

const MAX_LINHAS = 50;

export default function Historico({ capturas, selecionada, selecionar }) {
  const linhas = [...capturas].reverse().slice(0, MAX_LINHAS);

  return (
    <section className="card">
      <h2>
        Histórico <span className="etiqueta">últimas {Math.min(capturas.length, MAX_LINHAS)} de {capturas.length}</span>
      </h2>
      {!linhas.length ? (
        <p className="vazio">Nenhuma captura registrada.</p>
      ) : (
        <div className="tabela-rolagem">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Data/hora</th>
                <th>Origem</th>
                <th className="num">Ovos</th>
                <th className="num">Confiança</th>
                <th className="num">Captura</th>
                <th className="num">Inferência</th>
                <th className="num">Tamanho</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((c) => (
                <tr
                  key={c.id}
                  className={c.id === selecionada ? "sel" : ""}
                  onClick={() => c.foto && selecionar(c.id)}
                  style={{ cursor: c.foto ? "pointer" : "default" }}
                >
                  <td>{c.id}</td>
                  <td>{fmtDataHora(c.inicio)}</td>
                  <td>{c.origem === "auto" ? "automática" : "manual"}</td>
                  <td className="num forte">{c.ovos ?? "—"}</td>
                  <td className="num">{fmtPct(c.conf_media)}</td>
                  <td className="num">{fmtMs(c.tempo_captura_ms)}</td>
                  <td className="num">{fmtMs(c.tempo_inferencia_ms)}</td>
                  <td className="num">{fmtBytes(c.bytes)}</td>
                  <td>
                    {c.status === "ok" ? (
                      <span className="tag ok">ok</span>
                    ) : c.status === "erro" ? (
                      <span className="tag ruim" title={c.erro}>
                        erro
                      </span>
                    ) : (
                      <span className="tag neutro">em andamento</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
