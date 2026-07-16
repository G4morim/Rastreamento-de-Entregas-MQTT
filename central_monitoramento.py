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
import time
from datetime import datetime

import paho.mqtt.client as mqtt

import config
import historico

# Estado em memória: { id_entregador: {dados consolidados} }
frota = {}

# ----------------------------- Cores ANSI -----------------------------
RESET = "\033[0m"
VERMELHO = "\033[31m"
VERDE = "\033[32m"
AMARELO = "\033[33m"
CIANO = "\033[36m"
CINZA = "\033[90m"


def _habilitar_ansi():
    """Habilita sequências ANSI no console do Windows 10+ (no-op em Unix)."""
    if os.name == "nt":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # 7 = PROCESSED_OUTPUT | WRAP_AT_EOL | VIRTUAL_TERMINAL_PROCESSING
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)


def colorir(texto: str, cor: str) -> str:
    return f"{cor}{texto}{RESET}"


def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


LARGURA = 96


def _cor_status(status: str, offline: bool) -> str:
    if offline:
        return VERMELHO
    if status == "entregue" or status == "finalizado":
        return VERDE
    if status == "offline_inesperado":
        return VERMELHO
    if status == "pausado":
        return CIANO
    if status in ("em_transito", "proximo_ao_destino", "saiu_para_entrega"):
        return AMARELO
    return CINZA


def desenhar_painel():
    limpar_tela()
    print("=" * LARGURA)
    print(" CENTRAL DE MONITORAMENTO DE ENTREGAS  |  Protocolo: MQTT")
    print(f" Broker: {config.BROKER_HOST}:{config.porta_efetiva()}"
          f"   |   {datetime.now().strftime('%H:%M:%S')}")
    print("=" * LARGURA)

    if not frota:
        print("\n  Aguardando entregadores se conectarem...\n")
        print("=" * LARGURA)
        return

    cabecalho = (f"{'ENTREGADOR':<11}{'STATUS':<20}{'POSIÇÃO (lat, lon)':<20}"
                 f"{'BAT.':<6}{'VEL':<5}{'SINAL':<8}{'DIST':<8}{'ETA':<8}"
                 f"{'ATUALIZADO':<10}")
    print(cabecalho)
    print("-" * LARGURA)

    agora = time.time()
    for id_ent, dados in sorted(frota.items()):
        ultima = dados.get("ultima_msg", 0)
        offline = (agora - ultima) > config.TIMEOUT_OFFLINE if ultima else False

        status = dados.get("status", "—")
        status_txt = "SEM SINAL" if offline else status
        status_cell = colorir(f"{status_txt:<20}", _cor_status(status, offline))

        pos = dados.get("pos", "—")

        bat = dados.get("bateria")
        if bat is None:
            bat_cell = f"{'—':<6}"
        elif bat < config.LIMIAR_BATERIA_BAIXA:
            bat_cell = colorir(f"{str(bat) + '%!':<6}", VERMELHO)
        else:
            bat_cell = f"{str(bat) + '%':<6}"

        vel = dados.get("velocidade")
        vel_cell = f"{(str(vel) if vel is not None else '—'):<5}"
        sinal = dados.get("sinal")
        sinal_cell = f"{(str(sinal) + 'dBm' if sinal is not None else '—'):<8}"

        dist = dados.get("distancia")
        dist_cell = f"{(f'{dist:.1f}km' if dist is not None else '—'):<8}"
        eta = dados.get("eta")
        eta_cell = f"{(f'{eta:.0f}min' if eta is not None else '—'):<8}"

        if ultima:
            seg = int(agora - ultima)
            atualizado = f"{seg}s atrás"
        else:
            atualizado = "—"
        atualizado_cell = colorir(f"{atualizado:<10}",
                                  VERMELHO if offline else CINZA)

        print(f"{id_ent:<11}{status_cell}{pos:<20}{bat_cell}"
              f"{vel_cell}{sinal_cell}{dist_cell}{eta_cell}{atualizado_cell}")

    desenhar_resumo(agora)
    print("=" * LARGURA)
    print(" Ctrl+C para encerrar.")


def desenhar_resumo(agora: float):
    """Rodapé com estatísticas consolidadas da frota."""
    total = len(frota)
    entregues = sum(1 for d in frota.values()
                    if d.get("status") in ("entregue", "finalizado"))
    offline = sum(1 for d in frota.values()
                  if d.get("ultima_msg")
                  and (agora - d["ultima_msg"]) > config.TIMEOUT_OFFLINE)
    baterias = [d["bateria"] for d in frota.values()
                if d.get("bateria") is not None]
    media_bat = f"{sum(baterias) / len(baterias):.0f}%" if baterias else "—"
    dist_total = sum(d["distancia"] for d in frota.values()
                     if d.get("distancia") is not None)

    print("-" * LARGURA)
    print(f" Frota: {total}   Entregues: {entregues}   "
          f"Offline: {offline}   Bateria média: {media_bat}   "
          f"Distância total: {dist_total:.1f}km")


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

    # A central também "ouve" os comandos que ela mesma envia (assina
    # entregas/#). Ignora-os para não poluir o painel nem o histórico.
    if tipo == config.TOPIC_COMANDO:
        return

    registro = frota.setdefault(id_ent, {})
    registro["ultima_msg"] = time.time()
    historico.registrar(id_ent, tipo, dados)

    if tipo == config.TOPIC_LOCALIZACAO:
        registro["pos"] = f"{dados['lat']:.4f}, {dados['lon']:.4f}"
    elif tipo == config.TOPIC_STATUS:
        registro["status"] = dados.get("status", "—")
    elif tipo == config.TOPIC_TELEMETRIA:
        registro["bateria"] = dados.get("bateria_pct")
        registro["velocidade"] = dados.get("velocidade_kmh")
        registro["sinal"] = dados.get("sinal_dbm")
        registro["distancia"] = dados.get("distancia_km")
        registro["eta"] = dados.get("eta_min")


def main():
    _habilitar_ansi()
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="central-monitoramento",
    )
    client.on_connect = on_connect
    client.on_message = on_message

    if config.USAR_TLS:
        client.tls_set()

    # Autenticação usuário/senha (se MQTT_USER/MQTT_PASS estiverem setados).
    config.aplicar_credenciais(client)

    client.connect(config.BROKER_HOST, config.porta_efetiva(), config.KEEPALIVE)
    client.loop_start()   # rede em thread separada; o painel redesenha aqui

    try:
        # Redesenha 1x por segundo para manter "ATUALIZADO" e "SEM SINAL"
        # corretos mesmo quando nenhuma mensagem nova chega.
        while True:
            desenhar_painel()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando central...")
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
