"""Testes da persistência em SQLite e do relatório."""
import sqlite3

import pytest

import config
import historico
import relatorio


@pytest.fixture(autouse=True)
def db_temporario(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARQUIVO_DB", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "HISTORICO_CSV", False)
    historico.reset()
    yield
    historico.reset()


def test_registrar_persiste_evento():
    historico.registrar("ENT-001", "status", {"status": "entregue"})
    conn = sqlite3.connect(config.ARQUIVO_DB)
    linhas = conn.execute("SELECT entregador, tipo, resumo FROM eventos").fetchall()
    conn.close()
    assert linhas == [("ENT-001", "status", "entregue")]


def test_resumir_telemetria():
    r = historico.resumir("telemetria",
                          {"bateria_pct": 50, "velocidade_kmh": 30, "sinal_dbm": -70})
    assert r == "bat=50 vel=30 sinal=-70"


def test_csv_opcional(monkeypatch, tmp_path):
    csv_path = tmp_path / "export.csv"
    monkeypatch.setattr(config, "HISTORICO_CSV", True)
    monkeypatch.setattr(config, "ARQUIVO_HISTORICO", str(csv_path))
    historico.registrar("ENT-002", "status", {"status": "em_transito"})
    assert csv_path.exists()
    conteudo = csv_path.read_text(encoding="utf-8")
    assert "ENT-002" in conteudo and "em_transito" in conteudo


def test_relatorio_conta_entregas(capsys):
    historico.registrar("ENT-001", "status", {"status": "saiu_para_entrega"})
    historico.registrar("ENT-001", "status", {"status": "entregue"})
    historico.registrar("ENT-002", "status", {"status": "offline_inesperado"})
    conn = sqlite3.connect(config.ARQUIVO_DB)
    conn.row_factory = sqlite3.Row
    relatorio.relatorio(conn)
    conn.close()
    saida = capsys.readouterr().out
    assert "Entregas concluídas : 1" in saida
    assert "Quedas inesperadas  : 1" in saida


def test_relatorio_ultimo_status_usa_ordem_de_insercao(capsys):
    # Dois status no mesmo segundo: o relatório deve refletir o ÚLTIMO inserido.
    historico.registrar("ENT-009", "status", {"status": "saiu_para_entrega"})
    historico.registrar("ENT-009", "status", {"status": "entregue"})
    conn = sqlite3.connect(config.ARQUIVO_DB)
    conn.row_factory = sqlite3.Row
    relatorio.relatorio(conn)
    conn.close()
    linhas = [l for l in capsys.readouterr().out.splitlines() if "ENT-009" in l]
    assert linhas and "entregue" in linhas[-1]
