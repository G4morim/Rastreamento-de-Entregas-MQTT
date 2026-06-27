"""
entregador.py
-------------
Simula um ENTREGADOR (dispositivo IoT móvel) em rota de entrega.

Cada entregador é um cliente MQTT que PUBLICA, em tempo real:
  - localizacao : coordenadas GPS (latitude/longitude) ao longo da rota
  - status      : etapa da entrega (saiu_para_entrega, em_transito, entregue...)
  - telemetria  : bateria, velocidade e qualidade do sinal

Uso:
    python entregador.py ENT-001
    python entregador.py ENT-002 --intervalo 2

Abra vários terminais com IDs diferentes para simular uma frota.
"""

import argparse
import json
import random
import signal
import sys
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

import config

# Estados possíveis de uma entrega, em ordem de progressão
FLUXO_STATUS = [
    "saiu_para_entrega",
    "em_transito",
    "proximo_ao_destino",
    "entregue",
]

# Pontos de uma rota fictícia (Alegrete/RS -> destino). Lat/Lon aproximados.
# Em produção, isto viria do GPS real do dispositivo.
ROTA = [
    (-29.7833, -55.7917),
    (-29.7861, -55.7889),
    (-29.7895, -55.7854),
    (-29.7930, -55.7820),
    (-29.7968, -55.7791),
    (-29.8005, -55.7763),
]


class Entregador:
    def __init__(self, id_entregador: str, intervalo: int):
        self.id = id_entregador
        self.intervalo = intervalo
        self.bateria = random.randint(70, 100)
        self.indice_rota = 0
        self.indice_status = 0
        self.rodando = True

        # --- Cria o cliente MQTT (API de callbacks v2 do paho-mqtt) ---
        # client_id único evita que o broker derrube conexões duplicadas.
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"entregador-{self.id}",
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        # Last Will & Testament: se o entregador cair sem avisar (perda de
        # conexão, bateria acabou), o broker publica esta mensagem por ele.
        lwt = json.dumps({"id": self.id, "status": "offline_inesperado"})
        self.client.will_set(
            config.topico(self.id, config.TOPIC_STATUS),
            payload=lwt,
            qos=config.QOS_STATUS,
            retain=True,
        )

    # ----------------------------- Callbacks -----------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            print(f"[{self.id}] Conectado ao broker "
                  f"{config.BROKER_HOST}:{config.BROKER_PORT}")
        else:
            print(f"[{self.id}] Falha na conexão. Código: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        print(f"[{self.id}] Desconectado (código {reason_code}).")

    # ----------------------------- Publicações -----------------------------
    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def publica_localizacao(self):
        lat, lon = ROTA[self.indice_rota]
        # Pequeno ruído para simular movimento real do GPS
        lat += random.uniform(-0.0003, 0.0003)
        lon += random.uniform(-0.0003, 0.0003)

        payload = {
            "id": self.id,
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "timestamp": self._timestamp(),
        }
        self.client.publish(
            config.topico(self.id, config.TOPIC_LOCALIZACAO),
            json.dumps(payload),
            qos=config.QOS_LOCALIZACAO,
        )

        # Avança na rota (volta ao início quando chega ao fim)
        self.indice_rota = (self.indice_rota + 1) % len(ROTA)

    def publica_status(self):
        status = FLUXO_STATUS[self.indice_status]
        payload = {
            "id": self.id,
            "status": status,
            "timestamp": self._timestamp(),
        }
        self.client.publish(
            config.topico(self.id, config.TOPIC_STATUS),
            json.dumps(payload),
            qos=config.QOS_STATUS,
            retain=config.PUBLICAR_RETIDA_STATUS,
        )
        print(f"[{self.id}] >> status: {status}")

    def publica_telemetria(self):
        self.bateria = max(0, self.bateria - random.randint(0, 2))
        payload = {
            "id": self.id,
            "bateria_pct": self.bateria,
            "velocidade_kmh": random.randint(0, 60),
            "sinal_dbm": random.randint(-95, -55),
            "timestamp": self._timestamp(),
        }
        self.client.publish(
            config.topico(self.id, config.TOPIC_TELEMETRIA),
            json.dumps(payload),
            qos=config.QOS_TELEMETRIA,
        )

    # ----------------------------- Loop principal -----------------------------
    def iniciar(self):
        self.client.connect(config.BROKER_HOST, config.BROKER_PORT,
                            config.KEEPALIVE)
        self.client.loop_start()   # processa rede em thread separada
        time.sleep(1)              # dá tempo de conectar

        self.publica_status()      # anuncia "saiu_para_entrega"

        ciclos = 0
        try:
            while self.rodando:
                self.publica_localizacao()
                self.publica_telemetria()

                # A cada 4 ciclos, avança a etapa da entrega
                ciclos += 1
                if ciclos % 4 == 0 and self.indice_status < len(FLUXO_STATUS) - 1:
                    self.indice_status += 1
                    self.publica_status()
                    if FLUXO_STATUS[self.indice_status] == "entregue":
                        print(f"[{self.id}] Entrega concluída. Encerrando.")
                        break

                time.sleep(self.intervalo)
        finally:
            self._encerrar()

    def _encerrar(self):
        # Status final "limpo" (não foi queda) — sobrescreve o LWT retido
        payload = json.dumps({"id": self.id, "status": "finalizado"})
        self.client.publish(
            config.topico(self.id, config.TOPIC_STATUS),
            payload, qos=config.QOS_STATUS, retain=True,
        )
        time.sleep(0.5)
        self.client.loop_stop()
        self.client.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Simula um entregador IoT (MQTT)")
    parser.add_argument("id", nargs="?", default="ENT-001",
                        help="Identificador do entregador (ex.: ENT-001)")
    parser.add_argument("--intervalo", type=int, default=config.INTERVALO_ENVIO,
                        help="Segundos entre atualizações")
    args = parser.parse_args()

    entregador = Entregador(args.id, args.intervalo)

    # Ctrl+C encerra de forma limpa
    def _sair(sig, frame):
        entregador.rodando = False
    signal.signal(signal.SIGINT, _sair)

    print(f"Iniciando entregador {args.id} "
          f"(intervalo {args.intervalo}s). Ctrl+C para parar.\n")
    entregador.iniciar()


if __name__ == "__main__":
    main()
