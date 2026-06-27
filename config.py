"""
config.py
---------
Configurações centrais do sistema de rastreamento de entregas via MQTT.

Mantemos tudo em um único lugar para facilitar a troca de broker, ajuste de
QoS e a estrutura de tópicos sem precisar mexer na lógica dos scripts.
"""

# ---------------------------------------------------------------------------
# BROKER MQTT
# ---------------------------------------------------------------------------
# Você pode usar um broker público (sem instalar nada) ou um broker local
# (Mosquitto rodando na sua máquina). Veja o README para detalhes.
#
#   Público : "broker.hivemq.com"  ou  "test.mosquitto.org"
#   Local   : "localhost"
BROKER_HOST = "broker.hivemq.com"
BROKER_PORT = 1883          # 1883 = MQTT sem TLS | 8883 = MQTT com TLS
KEEPALIVE = 60              # segundos sem comunicação antes de enviar PINGREQ

# ---------------------------------------------------------------------------
# ESTRUTURA DE TÓPICOS
# ---------------------------------------------------------------------------
# Hierarquia: entregas/<id_entregador>/<tipo_de_dado>
#
# Exemplos publicados por um entregador:
#   entregas/ENT-001/localizacao
#   entregas/ENT-001/status
#   entregas/ENT-001/telemetria
#
# A central assina entregas/# para receber TUDO de TODOS os entregadores.
TOPIC_BASE = "entregas"
TOPIC_LOCALIZACAO = "localizacao"
TOPIC_STATUS = "status"
TOPIC_TELEMETRIA = "telemetria"

# Coringa que a central usa para escutar todos os entregadores e todos os dados
TOPIC_WILDCARD = f"{TOPIC_BASE}/#"


def topico(id_entregador: str, tipo: str) -> str:
    """Monta um tópico completo: entregas/<id>/<tipo>."""
    return f"{TOPIC_BASE}/{id_entregador}/{tipo}"


# ---------------------------------------------------------------------------
# QUALIDADE DE SERVIÇO (QoS)
# ---------------------------------------------------------------------------
#   QoS 0 -> "no máximo uma vez"   (dispara e esquece, mais rápido, pode perder)
#   QoS 1 -> "ao menos uma vez"    (garante entrega, pode duplicar)  <-- padrão
#   QoS 2 -> "exatamente uma vez"  (mais confiável e mais lento)
#
# Para rastreamento: localização aceita QoS 0 (chega a próxima logo), mas
# status de entrega usa QoS 1 porque não pode se perder.
QOS_LOCALIZACAO = 0
QOS_STATUS = 1
QOS_TELEMETRIA = 0

# ---------------------------------------------------------------------------
# PARÂMETROS DA SIMULAÇÃO
# ---------------------------------------------------------------------------
INTERVALO_ENVIO = 3        # segundos entre cada atualização de posição
PUBLICAR_RETIDA_STATUS = True   # status fica "retido" no broker (retained)
