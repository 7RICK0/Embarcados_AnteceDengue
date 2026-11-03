# AnteceDengue Station (G15)

Estação meteorológica IoT (ESP32 + FreeRTOS + MQTT) que monitora temperatura, umidade e chuva para antecipar condições favoráveis ao *Aedes aegypti*. Projeto de **Sistemas Embarcados** – CESAR School.

```
ESP32 (sensores + atuadores) --MQTT--> Mosquitto --> Backend FastAPI (SQLite) --WebSocket/REST--> Dashboard
        ^                                                                                              |
        +------------------------------ MQTT cmd (LED, intervalo, limiar) <---------------------------+
```

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `esp32-esp8266/` | Firmware PlatformIO (FreeRTOS), `diagram.json` + `wokwi.toml` |
| `applications/backend/` | API FastAPI + ponte MQTT + SQLite + testes |
| `applications/frontend/` | Dashboard (HTML/JS, tempo real via WebSocket) |
| `applications/tools/` | `simulate_station.py` – estação virtual p/ desenvolver sem hardware |
| `applications/mosquitto/` | Config do broker |
| `schematics/` | Tabela de ligações / esquemas |
| `docs/` | Protocolo MQTT, plano de testes, relatório |

## Rodando (sem hardware)
```bash
docker compose up --build            # broker :1883 + dashboard em http://localhost:8000
pip install paho-mqtt
python applications/tools/simulate_station.py --station rec02 --interval 3
```
Sem Docker: instale o Mosquitto, `cd applications/backend && pip install -r requirements.txt && uvicorn main:app`.

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

## Firmware
1. `cp esp32-esp8266/include/secrets.example.h esp32-esp8266/include/secrets.h` e preencha (**não commitar**).
2. Ajuste `MQTT_HOST` / `STATION_ID` em `include/config.h`.
3. Simulação: `pio run -e wokwi` e abra a pasta no Wokwi (VS Code ou wokwi.com). Hardware: `pio run -e wisdom -t upload`.

## Status
Ver `docs/TESTES.md` para o que foi validado e o que ainda precisa de teste em hardware.
