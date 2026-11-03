# Protocolo MQTT (v1)

Prefixo: `antecedengue/v1/{station_id}/`

| Tópico | Sentido | QoS | Retain | Payload |
|---|---|---|---|---|
| `telemetry` | ESP32 → broker | 0 no firmware (limitação PubSubClient); backend assina em 1 | não | JSON abaixo |
| `status` | ESP32 → broker | 1 (LWT) | **sim** | `online` / `offline` |
| `cmd` | dashboard → ESP32 | 1 | não | `{"led":bool,"interval_s":2..3600,"rain_alert_mm":>=0}` (campos opcionais) |
| `ack` | ESP32 → broker | 0 | não | config efetiva após aplicar `cmd` |

## Telemetria
```json
{"station_id":"rec01","timestamp":1760000000,"latitude":-8.0476,"longitude":-34.877,
 "temperature_c":28.5,"relative_humidity":70.2,"rainfall_mm":0.4,"battery_voltage":null}
```
`rainfall_mm` = chuva acumulada **desde a leitura anterior** (basculadas × `MM_PER_TIP`). `timestamp` = epoch UTC via NTP (0 se ainda sem NTP).

## Robustez
- LWT `offline` retido: o dashboard detecta queda sem polling.
- Reconexão Wi-Fi/MQTT com backoff exponencial (1 s → 15 s); fila FreeRTOS de 30 leituras como buffer offline; watchdog de 30 s.
- Para QoS1 real na publicação, trocar PubSubClient por AsyncMqttClient/esp-mqtt (ver riscos).

## Segurança (entrega)
`allow_anonymous false`, `password_file`, `acl_file` (estação só escreve em `.../{id}/#` e lê `.../{id}/cmd`). Credenciais em `secrets.h` (gitignored).

## IPv6 (obrigatório)
O edital cobra IPv6 em "Funcionamento" e dá bônus pela infraestrutura. O projeto trata como obrigatório:
- **Broker:** Mosquitto 2 sem `bind_address` escuta em IPv4 e IPv6. Em Docker: `docker-compose.ipv6.yml`.
- **Backend:** `MQTT_HOST` aceita IPv6 literal (`::1`); a API escuta em IPv6 com `uvicorn main:app --host ::`. `GET /api/health` devolve `"ip": "IPv6"|"IPv4"` e o dashboard mostra o badge.
- **Firmware (placa real):** `USE_IPV6` chama `WiFi.enableIPv6()` antes do `WiFi.begin` e imprime o endereço link-local. `MQTT_HOST` recebe o IPv6 do broker. **A validar na Wisdom:** depende da versão do arduino-esp32 e do PubSubClient conectarem a um endereço IPv6; se não conectar, documentar a tentativa e o motivo no relatório (e testar a pilha IPv6 com o simulador e o backend).
- **Rede:** o Wi-Fi/hotspot precisa distribuir IPv6; sem IPv6 global, usar endereços ULA/link-local numa rede local do grupo.
- **Medição:** repetir latência e perda de mensagens em IPv4 e IPv6 (ver `docs/TESTES.md`).
