"""Testes dos utilitários geográficos."""
import json

import pytest

import geo


def test_haversine_mesmo_ponto_e_zero():
    assert geo.haversine((-29.78, -55.79), (-29.78, -55.79)) == pytest.approx(0.0)


def test_haversine_distancia_conhecida():
    # ~1 grau de latitude ≈ 111 km
    d = geo.haversine((0.0, 0.0), (1.0, 0.0))
    assert d == pytest.approx(111.19, abs=0.5)


def test_comprimento_rota_soma_segmentos():
    pontos = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    esperado = (geo.haversine(pontos[0], pontos[1])
                + geo.haversine(pontos[1], pontos[2]))
    assert geo.comprimento_rota(pontos) == pytest.approx(esperado)


def test_distancias_restantes_decrescem_ate_zero():
    pontos = [(0.0, 0.0), (0.0, 1.0), (0.0, 2.0)]
    rest = geo.distancias_restantes(pontos)
    assert rest[-1] == 0.0
    assert rest[0] > rest[1] > rest[2]
    assert rest[0] == pytest.approx(geo.comprimento_rota(pontos))


def test_carregar_rota_aceita_pares_e_objetos(tmp_path):
    pares = tmp_path / "pares.json"
    pares.write_text(json.dumps([[-29.78, -55.79], [-29.79, -55.78]]))
    objs = tmp_path / "objs.json"
    objs.write_text(json.dumps([{"lat": -29.78, "lon": -55.79},
                                {"lat": -29.79, "lon": -55.78}]))
    assert geo.carregar_rota(str(pares)) == geo.carregar_rota(str(objs))


def test_carregar_rota_exige_dois_pontos(tmp_path):
    curta = tmp_path / "curta.json"
    curta.write_text(json.dumps([[-29.78, -55.79]]))
    with pytest.raises(ValueError):
        geo.carregar_rota(str(curta))


def test_rota_exemplo_do_projeto_carrega():
    pontos = geo.carregar_rota("rota_exemplo.json")
    assert len(pontos) >= 2
    assert geo.comprimento_rota(pontos) > 0
