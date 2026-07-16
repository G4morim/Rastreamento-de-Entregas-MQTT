"""Testes das funções puras de config.py."""
import importlib

import config
from tests.conftest import FakeClient


def test_topico_monta_hierarquia():
    assert config.topico("ENT-001", config.TOPIC_STATUS) == "entregas/ENT-001/status"
    assert config.topico("ENT-9", "localizacao") == "entregas/ENT-9/localizacao"


def test_wildcard_cobre_a_base():
    assert config.TOPIC_WILDCARD == f"{config.TOPIC_BASE}/#"


def test_porta_efetiva_respeita_tls(monkeypatch):
    monkeypatch.setattr(config, "USAR_TLS", False)
    assert config.porta_efetiva() == config.BROKER_PORT
    monkeypatch.setattr(config, "USAR_TLS", True)
    assert config.porta_efetiva() == config.BROKER_PORT_TLS


def test_aplicar_credenciais_com_usuario(monkeypatch):
    monkeypatch.setattr(config, "MQTT_USER", "frota")
    monkeypatch.setattr(config, "MQTT_PASS", "segredo")
    c = FakeClient()
    config.aplicar_credenciais(c)
    assert c.credenciais == ("frota", "segredo")


def test_aplicar_credenciais_anonimo_nao_seta(monkeypatch):
    monkeypatch.setattr(config, "MQTT_USER", None)
    c = FakeClient()
    config.aplicar_credenciais(c)
    assert c.credenciais is None


def test_env_override_broker(monkeypatch):
    """MQTT_BROKER deve sobrescrever o host ao reimportar o módulo."""
    monkeypatch.setenv("MQTT_BROKER", "localhost")
    recarregado = importlib.reload(config)
    try:
        assert recarregado.BROKER_HOST == "localhost"
    finally:
        monkeypatch.delenv("MQTT_BROKER", raising=False)
        importlib.reload(config)
