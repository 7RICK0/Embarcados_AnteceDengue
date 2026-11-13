#pragma once
// ---- Identificação / MQTT ----
#define STATION_ID   "rec01"
#define STATION_LAT  -8.0476f
#define STATION_LON  -34.8770f
// Wokwi não alcança localhost: use broker público (troque STATION_ID por algo único p/ não colidir).
#ifdef WIFI_WOKWI
  #define MQTT_HOST "broker.hivemq.com"
  #define WIFI_SSID_USED "Wokwi-GUEST"
  #define WIFI_PASS_USED ""
#else
  #define MQTT_HOST "192.168.0.10"   // IP do PC/Raspberry com o Mosquitto
  #define WIFI_SSID_USED WIFI_SSID
  #define WIFI_PASS_USED WIFI_PASS
#endif
#define MQTT_PORT 1883
// IPv6 (obrigatório no projeto, só na placa real; o Wokwi não simula IPv6).
// MQTT_HOST pode ser o IPv6 do broker (ex.: "fd00::10") ou um nome com registro AAAA.
// SPIKE: depende da versão do arduino-esp32 resolver/conectar em IPv6 com o PubSubClient. Validar na Wisdom.
#ifndef WIFI_WOKWI
  #define USE_IPV6 1
#endif
#define TOPIC_ROOT "antecedengue/v1/"

// ---- Pinos (mesmo mapeamento no Wokwi e na Wisdom: LED alerta GPIO4, LED/azul GPIO18, botão GPIO27) ----
#define PIN_LED_ALERT 4
#ifndef PIN_LED_LINK
  #define PIN_LED_LINK 18    // no ESP32 DevKit o env devkit troca para GPIO2 (LED azul da placa)
#endif
#define PIN_RAIN      27     // pluviômetro (reed) ou botão da placa simulando báscula
#define PIN_DHT       32     // só Wokwi (ADC1/GPIO32 ok com Wi-Fi)
#define PIN_POT       39     // deslizante da Wisdom (env wisdom_pot)
#define PIN_SDA       21     // I2C padrão da ESP32; o material só confirma o APDS-9960 (luz). T/UR da Wisdom: NÃO confirmado.
#define PIN_SCL       22

// ---- Parâmetros ----
#define DEFAULT_INTERVAL_S   10
#define DEFAULT_RAIN_ALERT   10.0f
#define MM_PER_TIP           0.2f   // PLACEHOLDER: calibrar com volume conhecido
#define RAIN_DEBOUNCE_MS     50
#define QUEUE_LEN            30     // buffer offline (~5 min a 10 s)
#define WDT_TIMEOUT_S        30
