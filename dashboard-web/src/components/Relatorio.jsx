import { useState } from "react";

export default function Relatorio() {
  const [email, setEmail] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [mensagem, setMensagem] = useState(null);

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
      <form className="form-relatorio" onSubmit={enviar}>
        <label className="campo campo-email">
          E-mail de destino
          <input type="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nome@exemplo.com" />
        </label>
        <button className="botao-principal botao-relatorio" type="submit" disabled={enviando}>
          {enviando ? "Enviando…" : "Gerar e enviar PDF"}
        </button>
      </form>
      {mensagem && <p className={mensagem.tipo === "erro" ? "msg-erro" : "msg-sucesso"} role="status">{mensagem.texto}</p>}
    </section>
  );
}
