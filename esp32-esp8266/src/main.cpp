// AnteceDengue Station – ESP32 + FreeRTOS + MQTT
// Tasks: sensor -> queue -> mqtt (publish) ; rain (ISR + counting semaphore) ; actuator (LEDs)
// Protocolo: ver docs/PROTOCOLO_MQTT.md
// ATENÇÃO: PubSubClient publica apenas em QoS0 (assina em QoS0/1). Ver docs.
#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include <esp_task_wdt.h>
#include "config.h"
#include "secrets.h"

#if defined(USE_DHT22)
  #include <DHT.h>
  static DHT dht(PIN_DHT, DHT22);
#elif defined(USE_HTU21D)
  #include <Wire.h>
  #include <Adafruit_HTU21DF.h>
  static Adafruit_HTU21DF htu;
#endif

struct Reading { uint32_t ts; float temp, hum, rain_mm; };

static QueueHandle_t qReadings;
static SemaphoreHandle_t semRain;      // counting: 1 "give" por báscula
static SemaphoreHandle_t cfgMutex;
static volatile uint32_t rainTips = 0; // acumulado desde a última leitura
static volatile uint32_t lastTipMs = 0;
static volatile bool mqttUp = false;

struct Config {
  uint32_t interval_s = DEFAULT_INTERVAL_S;
  float rain_alert = DEFAULT_RAIN_ALERT;
  bool led = false;
  bool alert = false;
} cfg;

static WiFiClient net;
static PubSubClient mqtt(net);
static String tTelemetry, tStatus, tCmd, tAck;

// ---------- Chuva: ISR -> semáforo contador -> task ----------
void IRAM_ATTR onRain() {
  uint32_t now = millis();
  if (now - lastTipMs < RAIN_DEBOUNCE_MS) return;
  lastTipMs = now;
  BaseType_t hp = pdFALSE;
  xSemaphoreGiveFromISR(semRain, &hp);
  if (hp) portYIELD_FROM_ISR();
}
void taskRain(void *) {
  for (;;) {
    if (xSemaphoreTake(semRain, portMAX_DELAY) == pdTRUE) {
      __atomic_fetch_add(&rainTips, 1, __ATOMIC_SEQ_CST);
    }
  }
}

// ---------- Sensor ----------
static bool readTH(float &t, float &h) {
#if defined(USE_DHT22)
  t = dht.readTemperature(); h = dht.readHumidity();
#elif defined(USE_HTU21D)
  t = htu.readTemperature(); h = htu.readHumidity();
#elif defined(USE_POT_SIM)
  int raw = analogRead(PIN_POT);   // deslizante da Wisdom simula T/UR enquanto não há sensor
  t = 20.0f + raw * 20.0f / 4095;  // 20–40 °C
  h = 40.0f + raw * 55.0f / 4095;  // 40–95 %
#else
  t = 25.0f; h = 60.0f;
#endif
  return !(isnan(t) || isnan(h));
}
static uint32_t nowEpoch() { time_t n = time(nullptr); return n > 1700000000 ? (uint32_t)n : 0; }

void taskSensor(void *) {
  esp_task_wdt_add(nullptr);
  for (;;) {
    uint32_t iv;
    xSemaphoreTake(cfgMutex, portMAX_DELAY); iv = cfg.interval_s; xSemaphoreGive(cfgMutex);
    Reading r{};
    r.ts = nowEpoch();
    if (readTH(r.temp, r.hum)) {
      uint32_t tips = __atomic_exchange_n(&rainTips, 0, __ATOMIC_SEQ_CST);
      r.rain_mm = tips * MM_PER_TIP;
      xSemaphoreTake(cfgMutex, portMAX_DELAY); cfg.alert = r.rain_mm >= cfg.rain_alert; xSemaphoreGive(cfgMutex);
      if (xQueueSend(qReadings, &r, 0) != pdTRUE) {   // fila cheia: descarta a mais antiga
        Reading drop;
        xQueueReceive(qReadings, &drop, 0);
        xQueueSend(qReadings, &r, 0);
      }
    } else {
      Serial.println("[sensor] leitura invalida");
    }
    // dorme em fatias de 1 s: interval_s pode passar do watchdog (WDT_TIMEOUT_S)
    for (uint32_t s = 0; s < iv; s++) {
      esp_task_wdt_reset();
      vTaskDelay(pdMS_TO_TICKS(1000));
    }
    esp_task_wdt_reset();
  }
}

// ---------- MQTT ----------
static void publishAck() {
  JsonDocument d;
  xSemaphoreTake(cfgMutex, portMAX_DELAY);
  d["interval_s"] = cfg.interval_s; d["rain_alert_mm"] = cfg.rain_alert; d["led"] = cfg.led;
  xSemaphoreGive(cfgMutex);
  char b[200];
  size_t n = serializeJson(d, b, sizeof b);
  mqtt.publish(tAck.c_str(), (const uint8_t *)b, n, false);
}
static void onMsg(char *topic, byte *payload, unsigned len) {
  JsonDocument d;
  if (deserializeJson(d, payload, len)) { Serial.println("[cmd] JSON invalido"); return; }
  xSemaphoreTake(cfgMutex, portMAX_DELAY);
  if (d["interval_s"].is<int>()) cfg.interval_s = constrain((int)d["interval_s"], 2, 3600);
  if (d["rain_alert_mm"].is<float>() || d["rain_alert_mm"].is<int>()) cfg.rain_alert = max(0.0f, d["rain_alert_mm"].as<float>());
  if (d["led"].is<bool>()) cfg.led = d["led"].as<bool>();
  xSemaphoreGive(cfgMutex);
  publishAck();
}
static bool connectMqtt() {
  String cid = String("antece-") + STATION_ID + "-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  bool ok = strlen(MQTT_USER)
    ? mqtt.connect(cid.c_str(), MQTT_USER, MQTT_PASS, tStatus.c_str(), 1, true, "offline")
    : mqtt.connect(cid.c_str(), nullptr, nullptr, tStatus.c_str(), 1, true, "offline");
  if (ok) {
    mqtt.publish(tStatus.c_str(), "online", true);
    mqtt.subscribe(tCmd.c_str(), 1);
    publishAck();   // backend aprende o limiar efetivo da placa (que volta ao padrão após reboot)
  }
  return ok;
}
void taskMqtt(void *) {
  esp_task_wdt_add(nullptr);
  uint32_t backoff = 1000;
  for (;;) {
    esp_task_wdt_reset();
    if (WiFi.status() != WL_CONNECTED) {
      mqttUp = false;
#if defined(USE_IPV6)
      WiFi.enableIpV6();   // antes do begin: pede endereço IPv6 (link-local e/ou global) ao conectar
#endif
      WiFi.begin(WIFI_SSID_USED, WIFI_PASS_USED);
      for (int i = 0; i < 20 && WiFi.status() != WL_CONNECTED; i++) { vTaskDelay(pdMS_TO_TICKS(500)); esp_task_wdt_reset(); }
      if (WiFi.status() == WL_CONNECTED) {
        configTime(0, 0, "pool.ntp.org", "time.google.com");
        Serial.println(WiFi.localIP());
#if defined(USE_IPV6)
        Serial.print("[ipv6] "); Serial.println(WiFi.localIPv6());   // confirma que o IPv6 subiu
#endif
      } else {
        vTaskDelay(pdMS_TO_TICKS(backoff));
        backoff = min<uint32_t>(backoff * 2, 15000);
        continue;
      }
    }
    if (!mqtt.connected()) {
      mqttUp = false;
      if (connectMqtt()) {
        backoff = 1000;
        Serial.println("[mqtt] conectado");
      } else {
        Serial.printf("[mqtt] falhou rc=%d\n", mqtt.state());
        vTaskDelay(pdMS_TO_TICKS(backoff));
        backoff = min<uint32_t>(backoff * 2, 15000);
        continue;
      }
    }
    mqttUp = true;
    mqtt.loop();
    Reading r;
    while (mqtt.connected() && xQueueReceive(qReadings, &r, 0) == pdTRUE) {
      JsonDocument d;
      d["station_id"] = STATION_ID;
      d["timestamp"] = r.ts;
      d["latitude"] = STATION_LAT;
      d["longitude"] = STATION_LON;
      d["temperature_c"] = serialized(String(r.temp, 2));
      d["relative_humidity"] = serialized(String(r.hum, 1));
      d["rainfall_mm"] = serialized(String(r.rain_mm, 2));
      d["battery_voltage"] = nullptr;   // sem ADC de bateria ainda
      char b[320];
      size_t n = serializeJson(d, b, sizeof b);
      if (!mqtt.publish(tTelemetry.c_str(), (const uint8_t *)b, n)) {
        xQueueSendToFront(qReadings, &r, 0);   // devolve p/ reenviar
        break;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// ---------- Atuadores ----------
void taskActuator(void *) {
  bool blink = false;
  for (;;) {
    bool alert, led;
    xSemaphoreTake(cfgMutex, portMAX_DELAY); alert = cfg.alert; led = cfg.led; xSemaphoreGive(cfgMutex);
    digitalWrite(PIN_LED_ALERT, (alert || led) ? HIGH : LOW);
    blink = !blink;
    digitalWrite(PIN_LED_LINK, mqttUp ? HIGH : blink);   // fixo = MQTT ok; piscando = sem conexão
    vTaskDelay(pdMS_TO_TICKS(500));
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_LED_ALERT, OUTPUT);
  pinMode(PIN_LED_LINK, OUTPUT);
  pinMode(PIN_RAIN, INPUT_PULLUP);
#if defined(USE_DHT22)
  dht.begin();
#elif defined(USE_HTU21D)
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!htu.begin()) Serial.println("[htu21d] nao encontrado");
#endif
  String base = String(TOPIC_ROOT) + STATION_ID + "/";
  tTelemetry = base + "telemetry"; tStatus = base + "status"; tCmd = base + "cmd"; tAck = base + "ack";
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMsg);
  mqtt.setBufferSize(512);
  mqtt.setKeepAlive(15);

  qReadings = xQueueCreate(QUEUE_LEN, sizeof(Reading));
  semRain = xSemaphoreCreateCounting(100, 0);
  cfgMutex = xSemaphoreCreateMutex();
  esp_task_wdt_init(WDT_TIMEOUT_S, true);
  attachInterrupt(digitalPinToInterrupt(PIN_RAIN), onRain, FALLING);

  xTaskCreate(taskRain, "rain", 2048, nullptr, 3, nullptr);
  xTaskCreate(taskSensor, "sensor", 4096, nullptr, 2, nullptr);
  xTaskCreate(taskMqtt, "mqtt", 8192, nullptr, 2, nullptr);
  xTaskCreate(taskActuator, "act", 2048, nullptr, 1, nullptr);
}
void loop() { vTaskDelay(portMAX_DELAY); }
