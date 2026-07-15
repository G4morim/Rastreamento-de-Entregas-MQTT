#  Rastreamento de Entregas com MQTT

Implementação prática do protocolo **MQTT** aplicado a um cenário de IoT móvel:
**rastreamento de entregas em tempo real**. Este projeto é o desdobramento
prático do estudo comparativo *"Avaliação Comparativa de Protocolos de
Comunicação em IoT: MQTT, HTTP e CoAP sob a Perspectiva de Desempenho"*
(Redes de Computadores — UNIPAMPA).

No estudo, o MQTT foi apontado como **a escolha mais equilibrada** para esse
cenário, com o melhor balanço entre desempenho, eficiência e escalabilidade —
ideal para muitos clientes móveis. Aqui esse resultado vira código rodando.

---

##  Índice

1. [Por que MQTT?](#-por-que-mqtt)
2. [Arquitetura](#-arquitetura)
3. [Funcionalidades](#-funcionalidades)
4. [Estrutura de tópicos MQTT](#-estrutura-de-tópicos-mqtt)
5. [Conceitos do MQTT aplicados](#-conceitos-do-mqtt-aplicados)
6. [Pré-requisitos](#-pré-requisitos)
7. [Instalação](#-instalação)
8. [Configuração](#-configuração)
9. [Como usar — passo a passo](#-como-usar--passo-a-passo)
10. [Exemplo de saída](#-exemplo-de-saída)
11. [Estrutura de arquivos](#-estrutura-de-arquivos)
12. [Solução de problemas](#-solução-de-problemas)
13. [Trabalhos futuros](#-trabalhos-futuros)
14. [Referências](#-referências)

---

##  Por que MQTT?

O MQTT (Message Queuing Telemetry Transport) foi o protocolo recomendado no
estudo porque resolve bem os desafios típicos da IoT: **recursos limitados**
(CPU, memória, bateria) e **redes com baixa largura de banda**.

| Característica | MQTT | HTTP | CoAP |
|---|---|---|---|
| Modelo | Publicação/Assinatura | Requisição/Resposta | Requisição/Resposta |
| Transporte | TCP (confiável, persistente) | TCP (por requisição) | UDP (rápido, sem garantia) |
| Cabeçalho | ~2 bytes | grande, em texto | ~4 bytes |
| Conexão | Única e persistente | Reaberta a cada requisição | Sem conexão |
| Ideal para | Redes instáveis, muitos clientes móveis | APIs Web tradicionais | Latência mínima crítica |

Resultados de desempenho do estudo (resumo geral):

| Protocolo | CPU (%) | Memória (MB) | Latência (ms) | Dados (KB) | Sucesso (%) |
|---|---|---|---|---|---|
| **MQTT** | 7.45 | 34.89 | 98.3 | 521.7 | 99.8 |
| HTTP | 11.94 | 65.12 | 243.5 | 1543.2 | 99.5 |
| CoAP | — | 38.43 | 87.9 | 506.8 | 98.7 |

> Para rastreamento de muitos entregadores simultâneos, o modelo
> publicação/assinatura do MQTT com uma única conexão persistente é o que
> melhor equilibra custo de recursos e confiabilidade.

---

## Arquitetura

O MQTT desacopla quem envia de quem recebe usando um intermediário central, o
**broker**. Os entregadores nunca falam diretamente com a central — tudo passa
pelo broker, organizado por **tópicos**.

```
   ┌──────────────┐        publish         ┌──────────────┐
   │ Entregador 1 │ ─────────────────────▶ │              │
   │ (publisher)  │   entregas/ENT-001/... │              │
   └──────────────┘                        │              │
                                           │    BROKER    │   subscribe          ┌──────────────────────┐
   ┌──────────────┐        publish         │     MQTT     │   entregas/#         │       CENTRAL DE      │
   │ Entregador 2 │ ─────────────────────▶ │  (HiveMQ/    │ ───────────────────▶ │     MONITORAMENTO     │
   │ (publisher)  │   entregas/ENT-002/... │  Mosquitto)  │                      │     (subscriber)      │
   └──────────────┘                        │              │                      └──────────────────────┘
                                           │              │
   ┌──────────────┐        publish         │              │
   │ Entregador N │ ─────────────────────▶ │              │
   └──────────────┘                        └──────────────┘
```

- **Entregador** (`entregador.py`) → cliente **publisher**: simula um
  dispositivo IoT móvel publicando GPS, status e telemetria.
- **Central** (`central_monitoramento.py`) → cliente **subscriber**: assina
  `entregas/#` e exibe um painel ao vivo de toda a frota.
- **Broker** → servidor público (HiveMQ/Mosquitto) ou local. Não precisa
  programar nada nele.

---

##  Funcionalidades

- **Rastreamento de localização em tempo real** — cada entregador publica
  coordenadas GPS (latitude/longitude) ao longo de uma rota.
- **Acompanhamento de status da entrega** — fluxo completo:
  `saiu_para_entrega → em_transito → proximo_ao_destino → entregue`.
- **Telemetria do dispositivo** — bateria, velocidade e qualidade do sinal,
  refletindo a preocupação com recursos limitados da IoT.
- **Frota multi-cliente** — basta abrir vários terminais com IDs diferentes
  para simular dezenas de entregadores simultâneos (1, 10, 50... como no estudo).
- **Painel de monitoramento ao vivo** — a central consolida a frota e redesenha
  a tabela a cada segundo, com colunas de **velocidade**, **sinal (dBm)** e
  **quando chegou a última mensagem** de cada entregador.
- **Detecção de "SEM SINAL"** — se um entregador fica mais de `TIMEOUT_OFFLINE`
  segundos sem publicar, a central o destaca como offline no painel.
- **Alerta de bateria baixa** — bateria abaixo de `LIMIAR_BATERIA_BAIXA` aparece
  destacada em vermelho (com `!`).
- **Estatísticas da frota** — rodapé com total de entregadores, quantos já
  entregaram, quantos estão offline e a bateria média.
- **Histórico em CSV** — cada evento recebido é gravado em
  `historico_entregas.csv` para relatório/análise posterior.
- **Cores no terminal** — status colorido por etapa (ANSI, funciona também no
  console do Windows 10+).
- **QoS configurável por tipo de dado** — localização em QoS 0 (velocidade),
  status em QoS 1 (garantia de entrega).
- **Mensagens retidas (retained)** — o último status de cada entregador fica
  guardado no broker; quem conecta depois já recebe o estado atual.
- **Last Will & Testament (LWT)** — se um entregador cai sem avisar (perda de
  sinal, bateria), o broker publica automaticamente `offline_inesperado`.
- **Reconexão automática** — se a rede cair, o entregador reconecta sozinho
  (backoff de 1s a 30s) e reanuncia o status atual à central.
- **TLS opcional** — conexão segura na porta 8883 ligando `MQTT_TLS=1`.
- **Configuração por variável de ambiente** — troque broker, porta e intervalo
  sem editar código (`MQTT_BROKER`, `MQTT_PORT`, `MQTT_INTERVALO`, `MQTT_TLS`).
- **Encerramento limpo** — `Ctrl+C` desconecta o cliente de forma controlada.

---

##  Estrutura de tópicos MQTT

Hierarquia: `entregas/<id_entregador>/<tipo_de_dado>`

| Tópico | Conteúdo | QoS | Retido |
|---|---|---|---|
| `entregas/ENT-001/localizacao` | `{ lat, lon, timestamp }` | 0 | não |
| `entregas/ENT-001/status` | `{ status, timestamp }` | 1 | sim |
| `entregas/ENT-001/telemetria` | `{ bateria_pct, velocidade_kmh, sinal_dbm }` | 0 | não |

A central usa o **coringa** `entregas/#` para receber tudo de todos os
entregadores de uma só vez. Coringas disponíveis no MQTT:

- `+` → um nível (ex.: `entregas/+/status` = status de **todos** os entregadores).
- `#` → todos os níveis a partir do ponto (ex.: `entregas/#` = absolutamente tudo).

Exemplo de payload de localização:

```json
{
  "id": "ENT-001",
  "lat": -29.7861,
  "lon": -55.7889,
  "timestamp": "2026-06-26T12:34:56.789+00:00"
}
```

---

##  Conceitos do MQTT aplicados

| Conceito | Onde aparece no projeto |
|---|---|
| **Publish/Subscribe** | Entregadores publicam, central assina — desacoplados pelo broker |
| **Tópicos hierárquicos** | `entregas/<id>/<tipo>` |
| **QoS 0 / 1** | `config.py`: localização (0) vs. status (1) |
| **Retained message** | Último status guardado no broker (`retain=True`) |
| **Last Will (LWT)** | `will_set()` em `entregador.py` |
| **Keepalive / PINGREQ** | `KEEPALIVE = 60` mantém a conexão persistente viva |
| **Conexão única persistente** | `loop_start()` mantém uma só conexão TCP aberta |

---

##  Pré-requisitos

- **Python 3.8+**
- **pip**
- Acesso à internet (para usar o broker público) **ou** o **Mosquitto**
  instalado localmente.

---

## 📥 Instalação

```bash
# 1. Clone ou baixe o projeto e entre na pasta
cd rastreamento-entregas-mqtt

# 2. (Recomendado) crie um ambiente virtual
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 3. Instale as dependências
pip install -r requirements.txt
```

A única dependência é a `paho-mqtt` (>= 2.0), biblioteca cliente MQTT em
Python — a mesma usada na metodologia do estudo.

---

## ⚙ Configuração

Tudo fica centralizado em **`config.py`**. Os ajustes mais comuns:

```python
BROKER_HOST = "broker.hivemq.com"   # broker público (padrão)
BROKER_PORT = 1883
INTERVALO_ENVIO = 3                 # segundos entre atualizações
QOS_LOCALIZACAO = 0
QOS_STATUS = 1
```

**Usar broker local em vez do público:** instale o Mosquitto, rode-o e troque
para:

```python
BROKER_HOST = "localhost"
```

### Variáveis de ambiente (sem editar `config.py`)

Os principais parâmetros aceitam override por variável de ambiente, com o mesmo
padrão do `config.py` como fallback:

| Variável | Efeito | Padrão |
|---|---|---|
| `MQTT_BROKER` | Host do broker | `broker.hivemq.com` |
| `MQTT_PORT` | Porta sem TLS | `1883` |
| `MQTT_PORT_TLS` | Porta com TLS | `8883` |
| `MQTT_TLS` | `1` liga TLS (usa a porta 8883) | `0` |
| `MQTT_INTERVALO` | Segundos entre atualizações | `3` |

```bash
# Exemplo: broker local com intervalo de 1s
MQTT_BROKER=localhost MQTT_INTERVALO=1 python entregador.py ENT-001

# Exemplo: conexão segura via TLS
MQTT_TLS=1 python central_monitoramento.py
```

Outros ajustes do painel ficam em `config.py`: `LIMIAR_BATERIA_BAIXA`,
`TIMEOUT_OFFLINE` e `ARQUIVO_HISTORICO`.

---

## Como usar — passo a passo

> Cada entregador e a central são processos separados. Use **um terminal por
> processo**.

### Opção A — Broker público (mais simples, sem instalar nada)

Já vem configurado para `broker.hivemq.com`. Vá direto para o passo 2.

### Opção B — Broker local (Mosquitto)

```bash
# Instalar (Ubuntu/Debian)
sudo apt-get install mosquitto mosquitto-clients

# Subir o broker
mosquitto -v        # -v mostra logs; rode em um terminal dedicado
```
E ajuste `BROKER_HOST = "localhost"` no `config.py`.

---

### Passo 1 — Suba o broker (só na Opção B)

```bash
mosquitto -v
```

### Passo 2 — Inicie a central de monitoramento

```bash
python central_monitoramento.py
```

Ela conecta, assina `entregas/#` e exibe o painel aguardando entregadores.

### Passo 3 — Inicie um ou mais entregadores (em outros terminais)

```bash
python entregador.py ENT-001
python entregador.py ENT-002 --intervalo 2
python entregador.py ENT-003 --broker localhost --repetir
```

Cada um percorre a rota, evolui o status e envia telemetria. A central
atualiza o painel automaticamente.

Flags disponíveis no entregador:

| Flag | Efeito |
|---|---|
| `--intervalo N` | Segundos entre atualizações |
| `--broker HOST` | Sobrescreve o broker na hora |
| `--porta N` | Sobrescreve a porta na hora |
| `--repetir` | Ao concluir a entrega, reinicia a rota em loop (demonstrações) |

### Passo 4 — Encerre

`Ctrl+C` em qualquer terminal encerra aquele processo de forma limpa.

---

##  Exemplo de saída

**Terminal do entregador:**

```
Iniciando entregador ENT-001 (intervalo 1s). Ctrl+C para parar.

[ENT-001] Conectado ao broker localhost:1883
[ENT-001] >> status: saiu_para_entrega
[ENT-001] >> status: em_transito
[ENT-001] >> status: proximo_ao_destino
[ENT-001] >> status: entregue
[ENT-001] Entrega concluída. Encerrando.
```

**Painel da central:**

```
========================================================================================
 CENTRAL DE MONITORAMENTO DE ENTREGAS  |  Protocolo: MQTT
 Broker: localhost:1883   |   12:34:56
========================================================================================
ENTREGADOR  STATUS              POSIÇÃO (lat, lon)      BAT.  VEL   SINAL   ATUALIZADO
----------------------------------------------------------------------------------------
ENT-001     entregue            -29.8004, -55.7765      56%   0     -63dBm  1s atrás
ENT-002     em_transito         -29.7930, -55.7820      18%!  42    -71dBm  0s atrás
ENT-003     SEM SINAL           -29.7895, -55.7854      74%   —     -80dBm  19s atrás
----------------------------------------------------------------------------------------
 Frota: 3   Entregues: 1   Offline: 1   Bateria média: 49%
========================================================================================
 Ctrl+C para encerrar.
```

No terminal, `entregue` aparece em verde, etapas em andamento em amarelo, e
`SEM SINAL`/bateria baixa em vermelho.

---

## Estrutura de arquivos

```
rastreamento-entregas-mqtt/
├── config.py                   # Configurações: broker, tópicos, QoS, simulação
├── entregador.py               # Publisher: simula um entregador IoT móvel
├── central_monitoramento.py    # Subscriber: painel ao vivo da frota
├── requirements.txt            # Dependência (paho-mqtt)
├── historico_entregas.csv      # Gerado pela central: log de eventos da frota
└── README.md                   # Este arquivo
```

---

##  Solução de problemas

| Problema | Causa provável | Solução |
|---|---|---|
| `ConnectionRefusedError` | Broker local não está rodando | Rode `mosquitto -v` ou volte para o broker público |
| Trava em "Aguardando entregadores" | Central e entregador em brokers diferentes | Garanta o mesmo `BROKER_HOST` nos dois |
| Timeout / sem conexão no público | Firewall bloqueando a porta 1883 | Teste em outra rede ou use broker local |
| `ModuleNotFoundError: paho` | Dependência não instalada | `pip install -r requirements.txt` |
| Mensagens duplicadas | Comportamento esperado do QoS 1 | Use QoS 0 onde duplicação não importa |

> **Privacidade:** o broker público é compartilhado por qualquer pessoa na
> internet. Não envie dados reais ou sensíveis nele. Para isso, use um broker
> local ou com autenticação/TLS.

---

## Trabalhos futuros

Alinhados às direções apontadas no estudo:

- ✅ **Segurança (TLS)** — já disponível via `MQTT_TLS=1` (porta 8883). Falta
  ainda a **autenticação** usuário/senha.
- ✅ **Resiliência em redes instáveis** — reconexão automática com backoff já
  implementada; falta um roteiro de testes de queda/reconexão.
- ✅ **Persistência de histórico** — eventos já gravados em CSV
  (`historico_entregas.csv`); evoluir para banco de dados e **dashboard web**.
- Simular **cenários adversos** (falhas em ambientes urbanos, perda de sinal).
- Comparar, no mesmo cenário, as variantes HTTP e CoAP do estudo original.

---

## 📚 Referências

- OASIS — *MQTT Version 5.0 Specification*.
- Eclipse Paho — *paho-mqtt (Python client)*.
- HiveMQ — *MQTT Essentials*.
- Trabalho-base: *Avaliação Comparativa de Protocolos de Comunicação em IoT:
  MQTT, HTTP e CoAP sob a Perspectiva de Desempenho* — Redes de Computadores,
  UNIPAMPA.
