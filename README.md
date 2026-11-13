# AnteceDengue Station (G15)

[![CI](https://github.com/7RICK0/Embarcados_AnteceDengue/actions/workflows/ci.yml/badge.svg)](https://github.com/7RICK0/Embarcados_AnteceDengue/actions/workflows/ci.yml)

Estação meteorológica IoT (ESP32 + FreeRTOS + MQTT) que monitora temperatura, umidade e chuva para antecipar condições favoráveis ao *Aedes aegypti*. Projeto de **Sistemas Embarcados** – CESAR School.

```
ESP32 (sensores + atuadores) --MQTT--> Mosquitto --> Backend FastAPI (SQLite) --WebSocket/REST--> Dashboard
        ^                                                                                              |
        +------------------------------ MQTT cmd (LED, intervalo, limiar) <---------------------------+
```

## Integrantes
| Nome | GitHub | Papel |
|---|---|---|
| Artur Souto Maior Pifano Montalvão | [ArturSouto](https://github.com/ArturSouto) | Montagem física na protoboard e testes do circuito |
| Eduardo Roma | | Relatório técnico (modelo CSBC) e esquemáticos |
| Erick Acioli Belo (representante) | [7RICK0](https://github.com/7RICK0) | Coordenação e repositório; firmware (FreeRTOS e MQTT), back-end, dashboard, integração, IPv6 e CI |
| Lui Manso | | Testes e medições (latência e perda em IPv4/IPv6) e calibração do pluviômetro |
| Rodrigo Lucena | | Semáforo de risco (LED RGB) e apresentação na Mostra |

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `esp32-esp8266/` | Firmware PlatformIO (FreeRTOS), `diagram.json` + `wokwi.toml` |
| `applications/backend/` | API FastAPI + ponte MQTT + SQLite + testes |
| `applications/frontend/` | Dashboard (HTML/JS, tempo real via WebSocket) |
| `applications/tools/` | `simulate_station.py` – estação virtual p/ desenvolver sem hardware |
| `applications/mosquitto/` | Config do broker |
| `schematics/` | Tabela de ligações (Wokwi e ESP32 DevKit), diagrama do Wokwi e imagem do circuito |
| `docs/` | Protocolo MQTT, plano de testes, evidências (`docs/evidencias/`) e relatório do Check Point |

## Rodando (sem hardware)
Caminho validado (sem Docker): instale o Mosquitto e rode o backend.
```bash
cd applications/backend && pip install -r requirements.txt && uvicorn main:app   # dashboard em http://localhost:8000
pip install paho-mqtt
python applications/tools/simulate_station.py --station rec02 --interval 3
```
Com Docker (ainda não validado, ver `docs/TESTES.md`): `docker compose up --build` sobe o broker na porta 1883 e o dashboard em http://localhost:8000.

## IPv6 (obrigatório)
```bash
docker compose -f docker-compose.yml -f docker-compose.ipv6.yml up --build   # Docker com IPv6 ligado
python applications/tools/simulate_station.py --host ::1 --station rec02      # simulador por IPv6
```
O dashboard mostra o badge **IPv6/IPv4** (versão de IP da conexão backend↔broker). Detalhes e pontos a validar em `docs/PROTOCOLO_MQTT.md`.

## Testes
```bash
cd applications/backend && pip install pytest httpx && pytest -q
```
O GitHub Actions roda os testes do backend e compila todos os ambientes do firmware a cada push.

## Firmware
1. `cp esp32-esp8266/include/secrets.example.h esp32-esp8266/include/secrets.h` e preencha (**não commitar**).
2. Ajuste `MQTT_HOST` / `STATION_ID` em `include/config.h`.
3. Simulação: `pio run -e wokwi`, abra `esp32-esp8266/` no VS Code com a extensão **Wokwi Simulator** e clique em ▶ no `diagram.json` (o `wokwi.toml` carrega o firmware compilado pelo PlatformIO; o editor do site wokwi.com não serve para este projeto).
4. Para ver a simulação no dashboard: rode o backend com `MQTT_HOST=broker.hivemq.com` (o firmware do Wokwi publica nesse broker público como `rec01`).

| Ambiente | Placa | Gravar |
|---|---|---|
| `devkit` | ESP32 DevKit na protoboard (placa do grupo), ligação em `schematics/LIGACOES.md` | `pio run -e devkit -t upload` |
| `wisdom` | BlackBoard Wisdom com sensor HTU21D | `pio run -e wisdom -t upload` |
| `wisdom_pot` | BlackBoard Wisdom sem sensor (deslizante simula T/UR) | `pio run -e wisdom_pot -t upload` |
| `wokwi` | Simulação | `pio run -e wokwi` |

## Status
Ver `docs/TESTES.md` para o que foi validado e o que ainda falta testar na placa. Relatório do Check Point: `docs/Relatorio_CheckPoint_G15.pdf`.
