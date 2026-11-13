"""Simula uma estação ESP32 (telemetria, LWT/status, cmd -> ack). Útil p/ desenvolver sem hardware.

  python simulate_station.py --host localhost --station rec02 --interval 5
  IPv6:  python simulate_station.py --host ::1 --station rec02      (ou o IPv6 do PC com o broker)
"""
import argparse
import json
import math
import random
import time

import paho.mqtt.client as mqtt

ROOT = "antecedengue/v1"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--user")
    ap.add_argument("--password")
    ap.add_argument("--station", default="rec02")
    ap.add_argument("--interval", type=float, default=5)
    ap.add_argument("--lat", type=float, default=-8.0476)
    ap.add_argument("--lon", type=float, default=-34.877)
    ap.add_argument("--count", type=int, default=0, help="0 = infinito")
    a = ap.parse_args()

    cfg = {"interval_s": a.interval, "rain_alert_mm": 10.0, "led": False}
    base = f"{ROOT}/{a.station}"
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{a.station}")
    if a.user:
        c.username_pw_set(a.user, a.password)
    c.will_set(f"{base}/status", "offline", qos=1, retain=True)

    def on_connect(cl, ud, fl, rc, pr=None):
        cl.publish(f"{base}/status", "online", qos=1, retain=True)
        cl.subscribe(f"{base}/cmd", 1)
        cl.publish(f"{base}/ack", json.dumps({"applied": {}, "cfg": cfg}), qos=1)

    def on_message(cl, ud, msg):
        try:
            d = json.loads(msg.payload)
            cfg.update({k: d[k] for k in ("led", "interval_s", "rain_alert_mm") if k in d})
            cl.publish(f"{base}/ack", json.dumps({"applied": d, "cfg": cfg}), qos=1)
            print("cmd aplicado:", cfg)
        except ValueError:
            pass

    c.on_connect, c.on_message = on_connect, on_message
    c.connect(a.host, a.port, 30)
    c.loop_start()
    n, rain_total = 0, 0.0
    try:
        while a.count == 0 or n < a.count:
            t = time.time()
            rain = round(random.choice([0, 0, 0, 0.2, 0.4, 2.0, 11.0]) if random.random() < 0.4 else 0, 2)
            payload = {
                "station_id": a.station, "timestamp": int(t),
                "latitude": a.lat, "longitude": a.lon,
                "temperature_c": round(28 + 5 * math.sin(t / 600) + random.uniform(-.3, .3), 2),
                "relative_humidity": round(70 + 15 * math.cos(t / 600) + random.uniform(-1, 1), 1),
                "rainfall_mm": rain, "battery_voltage": round(3.9 - n * 0.0005, 3),
            }
            c.publish(f"{base}/telemetry", json.dumps(payload), qos=1)
            n += 1
            time.sleep(cfg["interval_s"])
    except KeyboardInterrupt:
        pass
    c.publish(f"{base}/status", "offline", qos=1, retain=True).wait_for_publish(2)
    c.loop_stop()


if __name__ == "__main__":
    main()
