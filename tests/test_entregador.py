"""Testes do comportamento de publicação do entregador (sem broker)."""
import json

import pytest

import config
import entregador as ent
from tests.conftest import FakeClient


@pytest.fixture
def entregador():
    e = ent.Entregador("ENT-TST", intervalo=1)
    e.client = FakeClient()   # troca a rede por um cliente falso
    return e


def test_publica_localizacao_no_topico_certo(entregador):
    entregador.publica_localizacao()
    topico, payload, qos, _ = entregador.client.publicacoes[-1]
    assert topico == "entregas/ENT-TST/localizacao"
    assert qos == config.QOS_LOCALIZACAO
    dados = json.loads(payload)
    assert dados["id"] == "ENT-TST"
    assert "lat" in dados and "lon" in dados


def test_localizacao_avanca_e_da_a_volta_na_rota(entregador):
    total = len(ent.ROTA)
    for _ in range(total):
        entregador.publica_localizacao()
    # Após percorrer a rota inteira, o índice volta a zero
    assert entregador.indice_rota == 0


def test_status_publica_com_retain_e_qos1(entregador):
    entregador.publica_status()
    topico, payload, qos, retain = entregador.client.publicacoes[-1]
    assert topico == "entregas/ENT-TST/status"
    assert qos == config.QOS_STATUS
    assert retain is True
    assert json.loads(payload)["status"] == ent.FLUXO_STATUS[0]


def test_telemetria_bateria_nunca_negativa(entregador):
    entregador.bateria = 1
    for _ in range(20):
        entregador.publica_telemetria()
    assert entregador.bateria >= 0
    ultimo = json.loads(entregador.client.publicacoes[-1][1])
    assert ultimo["bateria_pct"] >= 0
    assert -95 <= ultimo["sinal_dbm"] <= -55
