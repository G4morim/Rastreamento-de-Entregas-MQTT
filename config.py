"""
config.py
---------
Configurações centrais do sistema de rastreamento de entregas via MQTT.

Mantemos tudo em um único lugar para facilitar a troca de broker, ajuste de
QoS e a estrutura de tópicos sem precisar mexer na lógica dos scripts.

Vários parâmetros aceitam override por variável de ambiente (útil para trocar
o broker ou ligar TLS sem editar este arquivo). Ex.:

    MQTT_BROKER=localhost python entregador.py ENT-001
    MQTT_TLS=1 python central_monitoramento.py
"""

import os

# ---------------------------------------------------------------------------
# BROKER MQTT
# ---------------------------------------------------------------------------
# Você pode usar um broker público (sem instalar nada) ou um broker local
# (Mosquitto rodando na sua máquina). Veja o README para detalhes.
#
#   Público : "broker.hivemq.com"  ou  "test.mosquitto.org"
#   Local   : "localhost"
#
# Cada valor tem um padrão sensato, mas pode ser sobrescrito via ambiente.
BROKER_HOST = os.getenv("MQTT_BROKER", "broker.hivemq.com")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))   # 1883 = sem TLS
BROKER_PORT_TLS = int(os.getenv("MQTT_PORT_TLS", "8883"))  # 8883 = com TLS
KEEPALIVE = 60              # segundos sem comunicação antes de enviar PINGREQ

# Segurança: ligue TLS com MQTT_TLS=1. Requer que o broker aceite conexões
# TLS na porta 8883 (o HiveMQ público aceita).
USAR_TLS = os.getenv("MQTT_TLS", "0") == "1"

# Autenticação usuário/senha. Deixe em branco para conectar anonimamente
# (padrão dos brokers públicos). Em um broker com credenciais, defina:
#   MQTT_USER=frota MQTT_PASS=segredo python central_monitoramento.py
MQTT_USER = os.getenv("MQTT_USER", "") or None
MQTT_PASS = os.getenv("MQTT_PASS", "") or None


def porta_efetiva() -> int:
    """Retorna a porta a usar conforme TLS esteja ligado ou não."""
    return BROKER_PORT_TLS if USAR_TLS else BROKER_PORT


def aplicar_credenciais(client) -> None:
    """Configura usuário/senha no cliente MQTT, se definidos via ambiente.

    Chamado antes de conectar tanto pelo entregador quanto pela central,
    mantendo a lógica de autenticação em um só lugar.
    """
    if MQTT_USER is not None:
        client.username_pw_set(MQTT_USER, MQTT_PASS)


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
TOPIC_COMANDO = "comando"       # central -> entregador (sentido inverso)

# "id" reservado para comandos enviados a TODOS os entregadores de uma vez.
ID_BROADCAST = "todos"

# Coringa que a central usa para escutar todos os entregadores e todos os dados
TOPIC_WILDCARD = f"{TOPIC_BASE}/#"


def topico(id_entregador: str, tipo: str) -> str:
    """Monta um tópico completo: entregas/<id>/<tipo>."""
    return f"{TOPIC_BASE}/{id_entregador}/{tipo}"


def topico_comando(id_entregador: str) -> str:
    """Tópico de comando de um entregador específico."""
    return topico(id_entregador, TOPIC_COMANDO)


def topico_comando_broadcast() -> str:
    """Tópico de comando ouvido por TODOS os entregadores."""
    return topico(ID_BROADCAST, TOPIC_COMANDO)


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
INTERVALO_ENVIO = int(os.getenv("MQTT_INTERVALO", "3"))  # seg. entre posições
PUBLICAR_RETIDA_STATUS = True   # status fica "retido" no broker (retained)

# Simulação de cenários adversos (ligada por --falhas no entregador).
# A cada ciclo, com esta probabilidade, o entregador sofre uma falha:
# perda de sinal (para de publicar) ou queda de conexão (dispara LWT).
PROB_FALHA = float(os.getenv("MQTT_PROB_FALHA", "0.15"))

# ---------------------------------------------------------------------------
# PAINEL DA CENTRAL
# ---------------------------------------------------------------------------
LIMIAR_BATERIA_BAIXA = 20   # abaixo disso, o painel destaca a bateria (alerta)
TIMEOUT_OFFLINE = 15        # seg. sem mensagem -> entregador marcado "SEM SINAL"

# Persistência do histórico da frota.
#   - SQLite (padrão): consultável depois com `python relatorio.py`.
#   - CSV (opcional): ligue com MQTT_HIST_CSV=1 para também gerar um .csv.
ARQUIVO_DB = os.getenv("MQTT_DB", "historico_entregas.db")   # banco SQLite
ARQUIVO_HISTORICO = "historico_entregas.csv"   # export CSV opcional/relatório
HISTORICO_CSV = os.getenv("MQTT_HIST_CSV", "0") == "1"
