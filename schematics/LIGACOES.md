# Ligações

Fonte dos pinos da Wisdom: material da disciplina "ESP32 Prototipagem" (slide 8, "E na RoboCore Wisdom?").

## Wisdom: confirmado no material
| Função | GPIO | Observação |
|---|---|---|
| LED da barra | 4 | usado como LED de alerta |
| Canal azul do LED RGB | 18 | usado como LED de link MQTT |
| Botão da placa | 27 | simula a báscula da chuva (INPUT_PULLUP, FALLING) |
| Potenciômetro deslizante | 39 (VN) | reserva: pode simular temperatura/umidade |
| Luminosidade | I2C (APDS-9960) | não é LDR; pinos I2C não listados no material |
| Sensor de som | 36 | **não ligar outro sinal nesse pino** |

## Ainda sem confirmação (ver "Driver BlackBoard Wisdom")
- Pinos **vermelho e verde** do LED RGB da placa (só o azul, GPIO18, está no material).
- Sensor de **temperatura e umidade** da placa: o material não cita nenhum. Se não existir, usar sensor do Laboratório Garagem (DHT22/DHT11 ou LM35) em pino ADC1/livre, ou o potenciômetro (GPIO39) como simulação.
- Pinos I2C do APDS-9960 e do possível sensor de T/UR (padrão da ESP32: SDA 21, SCL 22).

## Semáforo (proposta até confirmar o RGB da placa)
LED RGB do kit na protoboard, um resistor por canal: R = GPIO25, G = GPIO26, B = GPIO33 (pinos "seguros" do material). O amarelo vem de vermelho + verde. Se a cor ficar ruim, usar os 3 LEDs separados (vermelho, amarelo, verde) nos mesmos pinos.

## Wokwi
| Função | GPIO | Wokwi |
|---|---|---|
| LED alerta | 4 | LED vermelho + resistor |
| LED link MQTT | 18 | LED azul + resistor |
| Pluviômetro / botão | 27 | botão → GND (pull-up interno) |
| Temp/UR | 32 | DHT22 |

Regras: entradas analógicas só em ADC1 (GPIO32–39) por causa do Wi-Fi; pinos de boot (0, 2, 4, 5, 12, 15) pedem cuidado; HC-SR04 exige divisor 5 V→3,3 V no echo.
Arquivo do Wokwi: `esp32-esp8266/diagram.json` (cópia em `schematics/wokwi-diagram.json`; imagem do circuito em `schematics/wokwi-circuito.png`).
