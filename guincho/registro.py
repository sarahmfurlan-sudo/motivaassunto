"""Registro estruturado (SQLite) + linha do tempo de eventos para rastreabilidade."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime

from . import config

ESTRUTURA = """
CREATE TABLE IF NOT EXISTS solicitacoes (
    protocolo          TEXT PRIMARY KEY,
    criado_em          TEXT NOT NULL,
    canal              TEXT NOT NULL,          -- email | arquivo | voz
    origem_id          TEXT UNIQUE,            -- Message-ID, arquivo+linha... (evita duplicar)
    solicitante        TEXT,
    texto_original     TEXT NOT NULL,
    categoria          TEXT,
    tipo_veiculo       TEXT,
    tipo_guincho       TEXT,
    rodovia            TEXT,
    km                 REAL,
    sentido            TEXT,
    posicao            TEXT,
    motivo             TEXT,
    vitimas            INTEGER,
    carga_perigosa     INTEGER,
    placa              TEXT,
    prioridade         TEXT,
    resumo             TEXT,
    campos_faltantes   TEXT,
    confianca          REAL,
    justificativa_ia   TEXT,
    metodo             TEXT,                   -- ia:<modelo> | regras
    status             TEXT NOT NULL,          -- encaminhada | em_triagem | erro_encaminhamento
    base_responsavel   TEXT,
    responsavel        TEXT,
    email_responsavel  TEXT,
    motivo_destino     TEXT,
    latitude           REAL,
    longitude          REAL
);
CREATE TABLE IF NOT EXISTS eventos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo  TEXT NOT NULL REFERENCES solicitacoes(protocolo),
    quando     TEXT NOT NULL,
    evento     TEXT NOT NULL,
    detalhe    TEXT
);
CREATE INDEX IF NOT EXISTS ix_eventos_protocolo ON eventos(protocolo);
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


@contextmanager
def conexao():
    config.BANCO.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.BANCO)
    con.row_factory = sqlite3.Row
    con.executescript(ESTRUTURA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def buscar_por_origem(origem_id: str) -> dict | None:
    with conexao() as con:
        r = con.execute("SELECT * FROM solicitacoes WHERE origem_id = ?", (origem_id,)).fetchone()
        return dict(r) if r else None


def novo_protocolo(con) -> str:
    dia = datetime.now().strftime("%Y%m%d")
    n = con.execute("SELECT COUNT(*) FROM solicitacoes WHERE protocolo LIKE ?", (f"GUI-{dia}-%",)).fetchone()[0]
    return f"GUI-{dia}-{n + 1:04d}"


def inserir(registro: dict) -> str:
    with conexao() as con:
        protocolo = novo_protocolo(con)
        registro = {**registro, "protocolo": protocolo, "criado_em": agora()}
        if isinstance(registro.get("campos_faltantes"), list):
            registro["campos_faltantes"] = json.dumps(registro["campos_faltantes"], ensure_ascii=False)
        colunas = ", ".join(registro)
        marcas = ", ".join("?" for _ in registro)
        con.execute(f"INSERT INTO solicitacoes ({colunas}) VALUES ({marcas})", list(registro.values()))
        return protocolo


def atualizar_status(protocolo: str, status: str) -> None:
    with conexao() as con:
        con.execute("UPDATE solicitacoes SET status = ? WHERE protocolo = ?", (status, protocolo))


def registrar_evento(protocolo: str, evento: str, detalhe: str | dict = "") -> None:
    if isinstance(detalhe, dict):
        detalhe = json.dumps(detalhe, ensure_ascii=False)
    with conexao() as con:
        con.execute("INSERT INTO eventos (protocolo, quando, evento, detalhe) VALUES (?, ?, ?, ?)",
                    (protocolo, agora(), evento, detalhe))


def obter(protocolo: str) -> dict | None:
    with conexao() as con:
        r = con.execute("SELECT * FROM solicitacoes WHERE protocolo = ?", (protocolo.upper(),)).fetchone()
        if not r:
            return None
        d = dict(r)
        d["eventos"] = [dict(e) for e in con.execute(
            "SELECT quando, evento, detalhe FROM eventos WHERE protocolo = ? ORDER BY id", (d["protocolo"],))]
        return d


def pendentes_de_envio() -> list[dict]:
    with conexao() as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM solicitacoes WHERE status = 'erro_encaminhamento' ORDER BY protocolo")]


def listar(limite: int = 50) -> list[dict]:
    with conexao() as con:
        return [dict(r) for r in con.execute(
            "SELECT protocolo, criado_em, canal, prioridade, status, rodovia, km, tipo_veiculo, "
            "base_responsavel, resumo FROM solicitacoes ORDER BY criado_em DESC, protocolo DESC LIMIT ?",
            (limite,))]
