"""
historico.py
------------
Persistência do histórico de eventos da frota.

Evolui o antigo log em CSV para um banco **SQLite** consultável (ver
`relatorio.py`), mantendo o CSV como export opcional (`MQTT_HIST_CSV=1`).

A central chama `registrar(id, tipo, dados)` a cada mensagem recebida. A
gravação usa uma única conexão protegida por lock, pois a `on_message` do
paho roda em uma thread de rede separada.
"""

import csv
import json
import os
import sqlite3
import threading
from datetime import datetime

import config

_conn = None
_lock = threading.Lock()

_CRIAR_TABELA = """
CREATE TABLE IF NOT EXISTS eventos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    entregador  TEXT NOT NULL,
    tipo        TEXT NOT NULL,
    resumo      TEXT,
    payload     TEXT
)
"""


def _get_conn():
    global _conn
    if _conn is None:
        # check_same_thread=False: a mesma conexão é usada pela thread de rede.
        _conn = sqlite3.connect(config.ARQUIVO_DB, check_same_thread=False)
        _conn.execute(_CRIAR_TABELA)
        _conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ent ON eventos(entregador)")
        _conn.commit()
    return _conn


def resumir(tipo: str, dados: dict) -> str:
    """Gera um resumo textual legível do evento, por tipo de tópico."""
    formatadores = {
        config.TOPIC_LOCALIZACAO: lambda d: f"{d.get('lat')},{d.get('lon')}",
        config.TOPIC_STATUS: lambda d: d.get("status", ""),
        config.TOPIC_TELEMETRIA: lambda d: (
            f"bat={d.get('bateria_pct')} vel={d.get('velocidade_kmh')} "
            f"sinal={d.get('sinal_dbm')}"),
    }
    return formatadores.get(tipo, lambda d: json.dumps(d, ensure_ascii=False))(dados)


def registrar(id_ent: str, tipo: str, dados: dict) -> None:
    """Grava um evento no SQLite (e no CSV, se MQTT_HIST_CSV=1)."""
    ts = datetime.now().isoformat(timespec="seconds")
    resumo = resumir(tipo, dados)
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO eventos (timestamp, entregador, tipo, resumo, payload)"
            " VALUES (?, ?, ?, ?, ?)",
            (ts, id_ent, tipo, resumo, json.dumps(dados, ensure_ascii=False)),
        )
        conn.commit()

    if config.HISTORICO_CSV:
        _append_csv(ts, id_ent, tipo, resumo)


def _append_csv(ts: str, id_ent: str, tipo: str, resumo: str) -> None:
    novo = not os.path.exists(config.ARQUIVO_HISTORICO)
    with open(config.ARQUIVO_HISTORICO, "a", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        if novo:
            escritor.writerow(["timestamp", "id", "tipo", "resumo"])
        escritor.writerow([ts, id_ent, tipo, resumo])


def reset() -> None:
    """Fecha a conexão atual (usado em testes para trocar o banco)."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close()
            _conn = None
