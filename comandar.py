"""
comandar.py
-----------
Envia um comando da central para um entregador (ou para todos), demonstrando o
MQTT no sentido inverso: aqui a central PUBLICA e o entregador ASSINA.

Uso:
    python comandar.py ENT-001 pausar
    python comandar.py ENT-001 retomar
    python comandar.py ENT-002 reportar
    python comandar.py ENT-003 encerrar
    python comandar.py --todos pausar        # broadcast para toda a frota

Comandos: pausar | retomar | reportar | encerrar
"""

import argparse
import json
import sys
import time

import paho.mqtt.client as mqtt

import config

COMANDOS = ("pausar", "retomar", "reportar", "encerrar")


def enviar(id_entregador: str, comando: str, broadcast: bool = False) -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="central-comando")
    if config.USAR_TLS:
        client.tls_set()
    config.aplicar_credenciais(client)

    client.connect(config.BROKER_HOST, config.porta_efetiva(), config.KEEPALIVE)
    client.loop_start()

    topico = (config.topico_comando_broadcast() if broadcast
              else config.topico_comando(id_entregador))
    payload = json.dumps({"comando": comando})

    # QoS 1 garante a entrega do comando; espera o publish concluir.
    info = client.publish(topico, payload, qos=config.QOS_STATUS)
    info.wait_for_publish(timeout=5)
    time.sleep(0.2)

    alvo = "TODOS os entregadores" if broadcast else id_entregador
    print(f"Comando '{comando}' enviado para {alvo} (tópico {topico}).")

    client.loop_stop()
    client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Envia comandos a entregadores")
    parser.add_argument("id", nargs="?", default=None,
                        help="Identificador do entregador (ex.: ENT-001)")
    parser.add_argument("comando", choices=COMANDOS, help="Comando a enviar")
    parser.add_argument("--todos", action="store_true",
                        help="Envia o comando para todos os entregadores")
    args = parser.parse_args()

    if not args.todos and not args.id:
        parser.error("informe o ID do entregador ou use --todos")

    enviar(args.id or config.ID_BROADCAST, args.comando, broadcast=args.todos)


if __name__ == "__main__":
    main()
