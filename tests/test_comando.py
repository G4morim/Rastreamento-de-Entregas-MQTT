"""Testes dos tópicos de comando (sentido central -> entregador)."""
import config


def test_topico_comando_por_entregador():
    assert config.topico_comando("ENT-001") == "entregas/ENT-001/comando"


def test_topico_comando_broadcast():
    assert config.topico_comando_broadcast() == "entregas/todos/comando"


def test_broadcast_casa_com_wildcard_da_central():
    # A central assina 'entregas/#'; o tópico de broadcast deve estar coberto.
    base = config.TOPIC_WILDCARD.rstrip("#").rstrip("/")
    assert config.topico_comando_broadcast().startswith(base)
