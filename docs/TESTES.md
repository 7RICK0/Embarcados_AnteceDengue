# Testes e validação

## Já validado (ambiente de desenvolvimento, sem hardware)
- [x] Backend: 6 testes unitários (`pytest`) – persistência, alertas, payload inválido, LWT, tópico estranho, validação de comando.
- [x] E2E com broker MQTT local: simulador → backend → `/api/stations`; `POST /api/cmd` → simulador → `ack` registrado.

## NÃO validado ainda (fazer antes do Check Point)
- [ ] Firmware compila (`pio run -e wokwi` e `-e wisdom`) – **não foi compilado**; pode precisar de ajustes.
- [ ] Simulação no Wokwi (diagrama não foi aberto/ajustado visualmente).
- [ ] Pinos I2C/HTU21D e LEDs na Wisdom real.
- [ ] Dashboard no navegador (lógica escrita, não testada visualmente).
- [ ] IPv6: broker escutando em `::`; simulador com `--host ::1`; badge "IPv6" no dashboard; ESP32 com `WiFi.enableIPv6()` conectando ao broker por IPv6.

## Medições para o relatório
| Métrica | Como medir |
|---|---|
| Latência ponta a ponta | `timestamp` do ESP32 vs `recv_ts` do backend (NTP) |
| Perda de mensagens | contagem esperada (tempo/intervalo) vs recebida em 48–72 h |
| Precisão T/UR | comparar com termômetro de referência / INMET |
| Pluviômetro | despejar volume conhecido, calcular `MM_PER_TIP` |
| Disponibilidade | % de tempo `online` (tabela `events`) |
| IPv4 × IPv6 | repetir latência e perda nas duas pilhas; registrar o `ip` de `/api/health` |
