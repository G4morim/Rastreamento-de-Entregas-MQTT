"""
geo.py
------
Utilitários geográficos: distância entre coordenadas (haversine) e carga de
rotas a partir de um arquivo JSON.

Usado pelo entregador para calcular distância percorrida e um ETA aproximado
até o destino (último ponto da rota).
"""

import json
import math

RAIO_TERRA_KM = 6371.0

Ponto = tuple  # (lat, lon) em graus decimais


def haversine(p1, p2) -> float:
    """Distância em km entre dois pontos (lat, lon) pela fórmula de haversine."""
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * RAIO_TERRA_KM * math.asin(math.sqrt(a))


def comprimento_rota(pontos) -> float:
    """Soma dos segmentos consecutivos de uma rota, em km."""
    return sum(haversine(pontos[i], pontos[i + 1])
               for i in range(len(pontos) - 1))


def distancias_restantes(pontos):
    """Distância (km) de cada ponto até o fim da rota.

    Retorna uma lista onde `rest[i]` é a soma dos segmentos de `i` até o
    último ponto (o destino). `rest[-1]` é sempre 0.
    """
    rest = [0.0] * len(pontos)
    acumulado = 0.0
    for i in range(len(pontos) - 2, -1, -1):
        acumulado += haversine(pontos[i], pontos[i + 1])
        rest[i] = acumulado
    return rest


def carregar_rota(caminho: str):
    """Carrega uma rota de um JSON.

    Aceita tanto uma lista de pares `[lat, lon]` quanto de objetos
    `{"lat": ..., "lon": ...}`. Exige ao menos 2 pontos.
    """
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)

    pontos = []
    for p in dados:
        if isinstance(p, dict):
            pontos.append((float(p["lat"]), float(p["lon"])))
        else:
            pontos.append((float(p[0]), float(p[1])))

    if len(pontos) < 2:
        raise ValueError("A rota precisa de pelo menos 2 pontos.")
    return pontos
