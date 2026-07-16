"""Fixtures compartilhadas pelos testes."""
import os
import sys

# Garante que os módulos do projeto (na raiz) sejam importáveis nos testes.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)


class FakeClient:
    """Cliente MQTT falso: captura publish() sem tocar na rede.

    Usado para verificar quais tópicos/payloads o entregador publicaria,
    sem precisar de um broker.
    """

    def __init__(self):
        self.publicacoes = []          # lista de (topico, payload, qos, retain)
        self.credenciais = None
        self.subscricoes = []

    def publish(self, topico, payload=None, qos=0, retain=False):
        self.publicacoes.append((topico, payload, qos, retain))

    def username_pw_set(self, user, password=None):
        self.credenciais = (user, password)

    def subscribe(self, topico, qos=0):
        self.subscricoes.append((topico, qos))

    def socket(self):
        return None   # sem socket real: _derrubar_conexao vira no-op

    # No-ops usados pelo ciclo de vida, irrelevantes nos testes
    def will_set(self, *a, **k):
        pass

    def tls_set(self, *a, **k):
        pass
