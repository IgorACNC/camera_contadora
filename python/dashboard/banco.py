"""Histórico de capturas e configuração, guardados em SQLite."""

import json
import sqlite3
import threading
from pathlib import Path

COLUNAS = (
    "id", "inicio", "origem", "status", "erro", "ovos", "conf_media",
    "tempo_captura_ms", "tempo_inferencia_ms", "bytes", "foto", "foto_anotada", "modo",
)


class Banco:
    def __init__(self, caminho: Path):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(caminho, check_same_thread=False)
        self._con.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock, self._con:
            self._con.executescript(
                """
                CREATE TABLE IF NOT EXISTS capturas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inicio TEXT NOT NULL,
                    origem TEXT NOT NULL,
                    status TEXT NOT NULL,
                    erro TEXT,
                    ovos INTEGER,
                    conf_media REAL,
                    tempo_captura_ms REAL,
                    tempo_inferencia_ms REAL,
                    bytes INTEGER,
                    foto TEXT,
                    foto_anotada TEXT,
                    modo TEXT
                );
                CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
                """
            )

    def nova_captura(self, inicio: str, origem: str) -> int:
        with self._lock, self._con:
            cur = self._con.execute(
                "INSERT INTO capturas (inicio, origem, status) VALUES (?, ?, 'em_andamento')", (inicio, origem)
            )
            return cur.lastrowid

    def atualizar(self, cid: int, **campos) -> dict:
        invalidos = set(campos) - set(COLUNAS)
        if invalidos:
            raise ValueError(f"colunas inválidas: {invalidos}")
        sets = ", ".join(f"{k} = ?" for k in campos)
        with self._lock, self._con:
            self._con.execute(f"UPDATE capturas SET {sets} WHERE id = ?", (*campos.values(), cid))
        return self.captura(cid)

    def captura(self, cid: int) -> dict:
        with self._lock:
            row = self._con.execute("SELECT * FROM capturas WHERE id = ?", (cid,)).fetchone()
        return dict(row)

    def ultimas(self, limite: int) -> list[dict]:
        """As capturas mais recentes, da mais antiga para a mais nova."""
        with self._lock:
            rows = self._con.execute("SELECT * FROM capturas ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def marcar_interrompidas(self):
        """Capturas que ficaram 'em_andamento' porque o servidor caiu no meio."""
        with self._lock, self._con:
            self._con.execute(
                "UPDATE capturas SET status = 'erro', erro = 'servidor reiniciado' WHERE status = 'em_andamento'"
            )

    def ler_config(self, padrao: dict) -> dict:
        with self._lock:
            rows = self._con.execute("SELECT chave, valor FROM config").fetchall()
        salvo = {r["chave"]: json.loads(r["valor"]) for r in rows}
        return {k: salvo.get(k, v) for k, v in padrao.items()}

    def salvar_config(self, config: dict):
        with self._lock, self._con:
            self._con.executemany(
                "INSERT INTO config (chave, valor) VALUES (?, ?) "
                "ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor",
                [(k, json.dumps(v)) for k, v in config.items()],
            )
