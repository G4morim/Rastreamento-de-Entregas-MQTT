"""Testes do roteamento e da lógica de apresentação da central."""
import json
import types

import pytest

import config
import central_monitoramento as central


class FakeMsg:
    def __init__(self, topic, dados):
        self.topic = topic
        self.payload = json.dumps(dados).encode()


@pytest.fixture(autouse=True)
def frota_limpa(tmp_path, monkeypatch):
    """Zera o estado global e desvia o histórico para um arquivo temporário."""
    central.frota.clear()
    monkeypatch.setattr(config, "ARQUIVO_HISTORICO",
                        str(tmp_path / "hist.csv"))
    yield
    central.frota.clear()


def _entregar(topico, dados):
    central.on_message(None, None, FakeMsg(topico, dados))


def test_on_message_roteia_localizacao():
    _entregar("entregas/ENT-001/localizacao",
              {"lat": -29.7861, "lon": -55.7889})
    assert "ENT-001" in central.frota
    assert central.frota["ENT-001"]["pos"] == "-29.7861, -55.7889"


def test_on_message_roteia_status():
    _entregar("entregas/ENT-002/status", {"status": "entregue"})
    assert central.frota["ENT-002"]["status"] == "entregue"


def test_on_message_roteia_telemetria():
    _entregar("entregas/ENT-003/telemetria",
              {"bateria_pct": 15, "velocidade_kmh": 40, "sinal_dbm": -70})
    reg = central.frota["ENT-003"]
    assert reg["bateria"] == 15
    assert reg["velocidade"] == 40
    assert reg["sinal"] == -70


def test_on_message_ignora_payload_invalido():
    msg = types.SimpleNamespace(topic="entregas/ENT-004/status",
                                payload=b"{nao eh json")
    central.on_message(None, None, msg)
    assert "ENT-004" not in central.frota


def test_on_message_ignora_topico_curto():
    _entregar("entregas/semtipo", {"status": "x"})
    assert central.frota == {}


@pytest.mark.parametrize("status,offline,esperado", [
    ("entregue", False, central.VERDE),
    ("finalizado", False, central.VERDE),
    ("em_transito", False, central.AMARELO),
    ("saiu_para_entrega", False, central.AMARELO),
    ("offline_inesperado", False, central.VERMELHO),
    ("em_transito", True, central.VERMELHO),   # offline vence a etapa
])
def test_cor_status(status, offline, esperado):
    assert central._cor_status(status, offline) == esperado
