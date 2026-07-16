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


def test_telemetria_inclui_distancia_e_eta(entregador):
    entregador.publica_telemetria()
    dados = json.loads(entregador.client.publicacoes[-1][1])
    assert "distancia_km" in dados
    assert "eta_min" in dados                 # pode ser None se parado
    assert dados["distancia_km"] >= 0


def test_distancia_acumula_ao_andar(entregador):
    for _ in range(len(ent.ROTA)):
        entregador.publica_localizacao()
    assert entregador.distancia_percorrida > 0


def test_rota_customizada_e_usada():
    rota = [(-29.78, -55.79), (-29.79, -55.78), (-29.80, -55.77)]
    e = ent.Entregador("ENT-R", intervalo=1, rota=rota)
    e.client = FakeClient()
    assert e.rota == rota
    assert len(e.dist_restante) == len(rota)
    assert e.dist_restante[-1] == 0.0


class FakeComandoMsg:
    def __init__(self, comando, json_wrap=True):
        corpo = json.dumps({"comando": comando}) if json_wrap else comando
        self.payload = corpo.encode()


def test_comando_pausar_e_retomar(entregador):
    entregador._on_comando(None, None, FakeComandoMsg("pausar"))
    assert entregador.pausado is True
    # publicou status "pausado"
    assert json.loads(entregador.client.publicacoes[-1][1])["status"] == "pausado"

    entregador._on_comando(None, None, FakeComandoMsg("retomar"))
    assert entregador.pausado is False


def test_comando_encerrar_para_o_loop(entregador):
    assert entregador.rodando is True
    entregador._on_comando(None, None, FakeComandoMsg("encerrar"))
    assert entregador.rodando is False


def test_comando_aceita_texto_simples(entregador):
    entregador._on_comando(None, None, FakeComandoMsg("pausar", json_wrap=False))
    assert entregador.pausado is True


def test_comando_desconhecido_nao_altera_estado(entregador):
    entregador._on_comando(None, None, FakeComandoMsg("xyz"))
    assert entregador.pausado is False
    assert entregador.rodando is True


def test_falha_inicia_perda_de_sinal(entregador, monkeypatch):
    entregador.falhas = True
    entregador.prob_falha = 1.0            # força a falha
    # random.random() controla: 1º sorteio (falha) e 2º (tipo: >=0.4 = perda sinal)
    valores = iter([0.0, 0.9])
    monkeypatch.setattr(ent.random, "random", lambda: next(valores))
    monkeypatch.setattr(ent.random, "randint", lambda a, b: 3)
    entregador._talvez_falhar()
    assert entregador.ciclos_sem_sinal == 3


def test_falha_nao_ocorre_com_prob_zero(entregador, monkeypatch):
    entregador.falhas = True
    entregador.prob_falha = 0.0
    monkeypatch.setattr(ent.random, "random", lambda: 0.5)
    entregador._talvez_falhar()
    assert entregador.ciclos_sem_sinal == 0


def test_derrubar_conexao_sem_socket_nao_quebra(entregador):
    # FakeClient.socket() retorna None: deve ser no-op silencioso
    entregador._derrubar_conexao()
