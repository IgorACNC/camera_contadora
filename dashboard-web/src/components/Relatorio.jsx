import { useEffect, useState } from "react";

export default function Relatorio() {
  const [destinos, setDestinos] = useState(null);
  const [smtpConfigurado, setSmtpConfigurado] = useState(false);
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [mensagem, setMensagem] = useState(null);

  useEffect(() => {
    fetch("/api/relatorio/destinos")
      .then((r) => r.json())
      .then((dados) => {
        setDestinos(dados.destinos);
        setSmtpConfigurado(dados.smtp_configurado);
        setEmail(dados.destinos[0] ?? "");
      })
      .catch((erro) => setMensagem({ tipo: "erro", texto: erro.message }));
  }, []);

  async function enviar(event) {
    event.preventDefault();
    setEnviando(true);
    setMensagem(null);
    try {
      const resposta = await fetch("/api/relatorio/enviar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const dados = await resposta.json();
      if (!resposta.ok) throw new Error(dados.detail ?? `HTTP ${resposta.status}`);
      setMensagem({ tipo: "ok", texto: `Relatório enviado para ${dados.email}.` });
    } catch (erro) {
      setMensagem({ tipo: "erro", texto: erro.message });
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section className="card">
      <h2>Enviar relatório PDF</h2>
      <p className="vazio">O PDF inclui o resumo e o histórico de até 5.000 capturas do dashboard.</p>
      {destinos && !destinos.length ? (
        <p className="msg-erro">
          Nenhum destinatário configurado. Defina RELATORIO_DESTINOS no terminal do servidor (veja o README).
        </p>
      ) : destinos ? (
        <>
          {!smtpConfigurado && (
            <p className="msg-erro">SMTP não configurado no servidor: defina SMTP_HOST e SMTP_USER (veja o README).</p>
          )}
          <form className="form-relatorio" onSubmit={enviar}>
            <label className="campo campo-email">
              E-mail de destino
              <select value={email} onChange={(e) => setEmail(e.target.value)}>
                {destinos.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </label>
            <button className="botao-principal botao-relatorio" type="submit" disabled={enviando || !smtpConfigurado}>
              {enviando ? "Enviando…" : "Gerar e enviar PDF"}
            </button>
          </form>
        </>
      ) : null}
      {mensagem && <p className={mensagem.tipo === "erro" ? "msg-erro" : "msg-sucesso"} role="status">{mensagem.texto}</p>}
    </section>
  );
}
