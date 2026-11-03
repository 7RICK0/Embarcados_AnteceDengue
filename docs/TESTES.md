# Testes e validação

Última atualização: 03/11/2026. Só está marcado como validado o que foi **executado de verdade**. Evidências em `docs/evidencias/`.

## Validado (sem hardware)
- [x] **Firmware compila** nos dois ambientes (`pio run -e wokwi` e `pio run -e wisdom`) com `espressif32@7.0.1` fixado no `platformio.ini`. A 8.0.0 (out/2026) quebrou o build no CI, por isso a versão fixa.
- [x] **Backend**: 7 testes unitários (`pytest`) passando, local e no CI.
- [x] **Wokwi (VS Code)**: firmware sobe, conecta no Wi-Fi `Wokwi-GUEST` e no broker público `broker.hivemq.com` (`[mqtt] conectado`). Evidência: `wokwi-vscode-mqtt-conectado.png`.
- [x] **Ponta a ponta com o Wokwi**: estação `rec01` (Wokwi) → HiveMQ → backend → dashboard, com os valores do DHT22 simulado (24 °C / 40 %).
- [x] **Comando de descida no Wokwi**: botão "LED ligar" no dashboard → `cmd` → firmware respondeu `ack` `{"led":true}` em ~1 s. Evidência: `dashboard-wokwi-rec01-ack.jpg`.
- [x] **Dashboard no navegador**: cards, gráficos, lista de eventos, troca de estação, badge de IP e WebSocket "ao vivo"; sem erros no console. Alerta de chuva disparando com o simulador (`g15sim`).
- [x] **IPv6 em loopback**: broker escutando **só** em `[::1]:1884`; simulador e backend conectados por `::1`; API servida em `http://[::1]:8001`; `/api/health` → `"ip":"IPv6"`; `cmd` → `ack` por IPv6. Evidência: `dashboard-ipv6.jpg`.

## Observações dos testes
- O relógio do Wokwi fica ~600 s atrás do PC (`recv_ts - ts ≈ 600`). **Latência não pode ser medida no Wokwi**; só na placa real com NTP.
- O Wokwi não simula IPv6 (por isso `USE_IPV6` só liga fora do env `wokwi`, ver `config.h`).
- A rede usada no teste só tinha IPv6 link-local (sem IPv6 global), então não deu para testar IPv6 com broker na internet.
- Dashboard: corrigido XSS (nome de estação/eventos vindos do broker público eram inseridos como HTML).

## NÃO validado ainda
- [ ] Interação manual no Wokwi: apertar o botão de chuva (GPIO27) até passar do limiar e ver o LED vermelho; LED azul fixo com MQTT ok.
- [ ] `docker-compose.yml` e `docker-compose.ipv6.yml` (Docker Desktop não subiu na máquina de teste).
- [ ] Mosquitto real (o teste IPv6 usou o broker Python `amqtt` como substituto).
- [ ] **Placa real (Wisdom)**: Wi-Fi, IPv6 (`WiFi.enableIpV6()`), pinos I2C/sensor T/UR, LEDs.
- [ ] Semáforo RGB por nível de risco (pinos R/G da placa ainda sem confirmação).

## Medições para o relatório
| Métrica | Como medir |
|---|---|
| Latência ponta a ponta | `timestamp` do ESP32 vs `recv_ts` do backend (NTP; não usar o Wokwi) |
| Perda de mensagens | contagem esperada (tempo/intervalo) vs recebida em 48–72 h |
| Precisão T/UR | comparar com termômetro de referência / INMET |
| Pluviômetro | despejar volume conhecido, calcular `MM_PER_TIP` |
| Disponibilidade | % de tempo `online` (tabela `events`) |
| IPv4 × IPv6 | repetir latência e perda nas duas pilhas; registrar o `ip` de `/api/health` |
