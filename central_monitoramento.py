"""
central_monitoramento.py
------------------------
Simula a CENTRAL DE MONITORAMENTO da transportadora.

É um cliente MQTT que ASSINA o tópico coringa `entregas/#`, ou seja, recebe
TODAS as mensagens de TODOS os entregadores (localização, status, telemetria)
e mantém um painel ao vivo no terminal.

Uso:
    python central_monitoramento.py

Deixe rodando e inicie um ou mais entregadores em outros terminais.
"""

import json
import os
from datetime import datetime

import paho.mqtt.client as mqtt

import config

# Estado em memória: { id_entregador: {dados consolidados} }
frota = {}


def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def desenhar_painel():
    limpar_tela()
    print("=" * 78)
    print(" CENTRAL DE MONITORAMENTO DE ENTREGAS  |  Protocolo: MQTT")
    print(f" Broker: {config.BROKER_HOST}:{config.BROKER_PORT}"
          f"   |   {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 78)

    if not frota:
        print("\n  Aguardando entregadores se conectarem...\n")
        print("=" * 78)
        return

    cabecalho = f"{'ENTREGADOR':<12}{'STATUS':<22}{'POSIÇÃO (lat, lon)':<26}{'BAT.':<6}"
    print(cabecalho)
    print("-" * 78)

    for id_ent, dados in sorted(frota.items()):
        status = dados.get("status", "—")
        pos = dados.get("pos", "—")
        bat = dados.get("bateria")
        bat_str = f"{bat}%" if bat is not None else "—"
        print(f"{id_ent:<12}{status:<22}{pos:<26}{bat_str:<6}")

    print("=" * 78)
    print(" Ctrl+C para encerrar.")


# ----------------------------- Callbacks -----------------------------
def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Central conectada a {config.BROKER_HOST}. Assinando "
              f"'{config.TOPIC_WILDCARD}'...")
        # Assina o coringa: recebe tudo de todos os entregadores
        client.subscribe(config.TOPIC_WILDCARD, qos=config.QOS_STATUS)
    else:
        print(f"Falha ao conectar. Código: {reason_code}")


def on_message(client, userdata, msg):
    """Roteia cada mensagem conforme o tipo de tópico recebido."""
    try:
        dados = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        return

    # Tópico no formato: entregas/<id>/<tipo>
    partes = msg.topic.split("/")
    if len(partes) < 3:
        return
    id_ent, tipo = partes[1], partes[2]

    registro = frota.setdefault(id_ent, {})

    if tipo == config.TOPIC_LOCALIZACAO:
        registro["pos"] = f"{dados['lat']:.4f}, {dados['lon']:.4f}"
    elif tipo == config.TOPIC_STATUS:
        registro["status"] = dados.get("status", "—")
    elif tipo == config.TOPIC_TELEMETRIA:
        registro["bateria"] = dados.get("bateria_pct")

    desenhar_painel()


def main():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="central-monitoramento",
    )
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(config.BROKER_HOST, config.BROKER_PORT, config.KEEPALIVE)
    desenhar_painel()

    try:
        client.loop_forever()   # bloqueia e processa mensagens
    except KeyboardInterrupt:
        print("\nEncerrando central...")
        client.disconnect()


if __name__ == "__main__":
    main()
