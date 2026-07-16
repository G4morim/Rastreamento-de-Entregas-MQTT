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
    python entregador.py ENT-003 --broker localhost --repetir

Abra vários terminais com IDs diferentes para simular uma frota.
"""

import argparse
import json
import random
import signal
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

import config
import geo

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
    def __init__(self, id_entregador: str, intervalo: int,
                 broker: str = None, porta: int = None, repetir: bool = False,
                 rota=None):
        self.id = id_entregador
        self.intervalo = intervalo
        self.broker = broker or config.BROKER_HOST
        self.porta = porta or config.porta_efetiva()
        self.repetir = repetir
        self.bateria = random.randint(70, 100)
        self.indice_rota = 0
        self.indice_status = 0
        self.rodando = True
        self.pausado = False       # comando "pausar" congela a simulação
        self.ja_conectou = False   # distingue 1ª conexão de reconexões

        # Rota percorrida (padrão embutido ou carregada de arquivo) e métricas
        # derivadas: distância percorrida e restante até o destino (haversine).
        self.rota = rota or ROTA
        self.dist_restante = geo.distancias_restantes(self.rota)
        self.distancia_percorrida = 0.0
        self.velocidade = 0

        # --- Cria o cliente MQTT (API de callbacks v2 do paho-mqtt) ---
        # client_id único evita que o broker derrube conexões duplicadas.
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"entregador-{self.id}",
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_comando   # comandos da central

        # Resiliência: se a conexão cair, o paho tenta reconectar sozinho,
        # com backoff exponencial entre 1s e 30s.
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

        # Segurança opcional: TLS na porta 8883 (ligado via MQTT_TLS=1).
        if config.USAR_TLS:
            self.client.tls_set()

        # Autenticação usuário/senha (se MQTT_USER/MQTT_PASS estiverem setados).
        config.aplicar_credenciais(self.client)

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
            if self.ja_conectou:
                print(f"[{self.id}] Reconectado ao broker "
                      f"{self.broker}:{self.porta} — reanunciando status.")
            else:
                print(f"[{self.id}] Conectado ao broker "
                      f"{self.broker}:{self.porta}")
                self.ja_conectou = True
            # Assina os comandos vindos da central: os do próprio entregador
            # e os de broadcast (enviados a todos de uma vez).
            self.client.subscribe(config.topico_comando(self.id),
                                   qos=config.QOS_STATUS)
            self.client.subscribe(config.topico_comando_broadcast(),
                                   qos=config.QOS_STATUS)
            # (Re)anuncia o status atual: em uma primeira conexão anuncia
            # "saiu_para_entrega"; após uma queda, garante que a central
            # reflita imediatamente a etapa corrente da entrega.
            self.publica_status()
        else:
            print(f"[{self.id}] Falha na conexão. Código: {reason_code}")

    def _on_comando(self, client, userdata, msg):
        """Reage a comandos enviados pela central (sentido central -> entregador).

        Aceita payload JSON `{"comando": "pausar"}` ou texto simples `pausar`.
        Comandos: pausar, retomar, reportar, encerrar.
        """
        bruto = msg.payload.decode(errors="ignore").strip()
        try:
            comando = json.loads(bruto).get("comando", "")
        except json.JSONDecodeError:
            comando = bruto
        comando = comando.lower()

        if comando == "pausar":
            if not self.pausado:
                self.pausado = True
                print(f"[{self.id}] << comando: PAUSAR")
                self._publica_status_texto("pausado")
        elif comando == "retomar":
            if self.pausado:
                self.pausado = False
                print(f"[{self.id}] << comando: RETOMAR")
                self.publica_status()   # reanuncia a etapa real da entrega
        elif comando == "reportar":
            print(f"[{self.id}] << comando: REPORTAR")
            self.publica_status()
            self.publica_telemetria()
        elif comando == "encerrar":
            print(f"[{self.id}] << comando: ENCERRAR")
            self.rodando = False
        else:
            print(f"[{self.id}] << comando desconhecido: {comando!r}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"[{self.id}] Conexão perdida (código {reason_code}). "
                  f"Tentando reconectar automaticamente...")
        else:
            print(f"[{self.id}] Desconectado.")

    # ----------------------------- Publicações -----------------------------
    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def publica_localizacao(self):
        lat, lon = self.rota[self.indice_rota]
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

        # Acumula a distância do segmento percorrido e avança na rota
        # (volta ao início quando chega ao fim).
        proximo = (self.indice_rota + 1) % len(self.rota)
        self.distancia_percorrida += geo.haversine(
            self.rota[self.indice_rota], self.rota[proximo])
        self.indice_rota = proximo

    def publica_status(self):
        """Publica a etapa atual da entrega (fluxo de negócio)."""
        self._publica_status_texto(FLUXO_STATUS[self.indice_status])

    def _publica_status_texto(self, status: str):
        """Publica um status arbitrário (etapa da entrega ou 'pausado')."""
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
        self.velocidade = random.randint(0, 60)

        # ETA aproximado até o destino: distância restante / velocidade atual.
        restante = self.dist_restante[self.indice_rota]
        if self.velocidade > 0:
            eta_min = round(restante / self.velocidade * 60, 1)
        else:
            eta_min = None   # parado: ETA indeterminado

        payload = {
            "id": self.id,
            "bateria_pct": self.bateria,
            "velocidade_kmh": self.velocidade,
            "sinal_dbm": random.randint(-95, -55),
            "distancia_km": round(self.distancia_percorrida, 2),
            "eta_min": eta_min,
            "timestamp": self._timestamp(),
        }
        self.client.publish(
            config.topico(self.id, config.TOPIC_TELEMETRIA),
            json.dumps(payload),
            qos=config.QOS_TELEMETRIA,
        )

    # ----------------------------- Loop principal -----------------------------
    def iniciar(self):
        # connect_async + loop_start: a thread de rede cuida da conexão e das
        # reconexões automáticas sem bloquear o loop de simulação.
        self.client.connect_async(self.broker, self.porta, config.KEEPALIVE)
        self.client.loop_start()   # processa rede em thread separada
        time.sleep(1)              # dá tempo de conectar (on_connect anuncia)

        ciclos = 0
        try:
            while self.rodando:
                # Pausado por comando: mantém a conexão viva (para receber
                # "retomar"), mas não avança a rota nem publica dados.
                if self.pausado:
                    time.sleep(self.intervalo)
                    continue

                self.publica_localizacao()
                self.publica_telemetria()

                # A cada 4 ciclos, avança a etapa da entrega
                ciclos += 1
                if ciclos % 4 == 0 and self.indice_status < len(FLUXO_STATUS) - 1:
                    self.indice_status += 1
                    self.publica_status()
                    if FLUXO_STATUS[self.indice_status] == "entregue":
                        if self.repetir:
                            print(f"[{self.id}] Entrega concluída. "
                                  f"Reiniciando rota (--repetir).")
                            self._reiniciar_rota()
                            ciclos = 0
                        else:
                            print(f"[{self.id}] Entrega concluída. Encerrando.")
                            break

                time.sleep(self.intervalo)
        finally:
            self._encerrar()

    def _reiniciar_rota(self):
        """Volta ao início do fluxo para simular uma nova entrega (--repetir)."""
        self.indice_status = 0
        self.indice_rota = 0
        self.bateria = random.randint(70, 100)
        self.distancia_percorrida = 0.0
        self.publica_status()

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
    parser.add_argument("--broker", default=None,
                        help="Host do broker (sobrescreve config/env)")
    parser.add_argument("--porta", type=int, default=None,
                        help="Porta do broker (sobrescreve config/env)")
    parser.add_argument("--repetir", action="store_true",
                        help="Ao concluir a entrega, reinicia a rota em loop")
    parser.add_argument("--rota", default=None, metavar="ARQUIVO.json",
                        help="Carrega a rota de um arquivo JSON (lista de "
                             "[lat, lon] ou {lat, lon})")
    args = parser.parse_args()

    rota = None
    if args.rota:
        try:
            rota = geo.carregar_rota(args.rota)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
            parser.error(f"não foi possível carregar a rota '{args.rota}': {e}")

    entregador = Entregador(args.id, args.intervalo,
                            broker=args.broker, porta=args.porta,
                            repetir=args.repetir, rota=rota)

    # Ctrl+C encerra de forma limpa
    def _sair(sig, frame):
        entregador.rodando = False
    signal.signal(signal.SIGINT, _sair)

    print(f"Iniciando entregador {args.id} "
          f"(intervalo {args.intervalo}s"
          f"{', loop' if args.repetir else ''}). Ctrl+C para parar.\n")
    entregador.iniciar()


if __name__ == "__main__":
    main()
