import json
import os

os.environ["DISABLE_MQTT"] = "1"
os.environ["DB_PATH"] = ":memory:"

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def fresh_db():
    main.init_db(":memory:")
    main._status.clear()
    yield


def pub(station, kind, payload):
    raw = payload if isinstance(payload, bytes) else (
        payload.encode() if isinstance(payload, str) else json.dumps(payload).encode())
    return main.handle_message(f"antecedengue/v1/{station}/{kind}", raw)


def test_telemetry_stored_and_listed():
    r = pub("rec01", "telemetry", {"timestamp": 1700000000, "temperature_c": 28.5,
                                   "relative_humidity": 70, "rainfall_mm": 0.4, "battery_voltage": 3.9})
    assert r["type"] == "telemetry" and r["alert"] == []
    with TestClient(main.app) as c:
        st = c.get("/api/stations").json()
        assert st[0]["station_id"] == "rec01" and st[0]["temperature_c"] == 28.5
        hist = c.get("/api/telemetry", params={"station": "rec01"}).json()
        assert len(hist) == 1


def test_alert_rain_and_heat():
    r = pub("rec01", "telemetry", {"temperature_c": 36, "rainfall_mm": 12})
    assert set(r["alert"]) == {"chuva", "calor"}


def test_rain_alert_follows_board_ack():
    assert pub("rec01", "telemetry", {"rainfall_mm": 6})["alert"] == []
    pub("rec01", "ack", {"interval_s": 10, "rain_alert_mm": 5, "led": False})   # formato do firmware
    assert pub("rec01", "telemetry", {"rainfall_mm": 6})["alert"] == ["chuva"]
    assert pub("rec02", "telemetry", {"rainfall_mm": 6})["alert"] == []          # outra estação: padrão
    pub("rec02", "ack", {"applied": {}, "cfg": {"rain_alert_mm": 2.0}})          # formato do simulador
    assert pub("rec02", "telemetry", {"rainfall_mm": 3})["alert"] == ["chuva"]


def test_rain_alert_survives_restart(tmp_path):
    db = str(tmp_path / "t.db")
    main.init_db(db)
    pub("rec01", "ack", {"rain_alert_mm": 5})
    main._db.close()
    main.init_db(db)   # backend reiniciado
    assert pub("rec01", "telemetry", {"rainfall_mm": 6})["alert"] == ["chuva"]
    main._db.close()


def test_bad_ack_ignored():
    pub("rec01", "ack", "nao json")
    pub("rec01", "ack", {"rain_alert_mm": True})
    assert "rec01" not in main._rain_alert


def test_bad_payload_ignored_and_logged():
    assert pub("rec01", "telemetry", "{nao json") is None
    assert pub("rec01", "telemetry", "[1,2]") is None
    with TestClient(main.app) as c:
        ev = c.get("/api/events").json()
        assert any(e["kind"] == "bad_payload" for e in ev)


def test_status_lwt():
    assert pub("rec01", "status", "offline")["status"] == "offline"
    assert main._status["rec01"] == "offline"
    assert pub("rec01", "status", "lixo") is None


def test_foreign_topic_ignored():
    assert main.handle_message("outro/topico/x/telemetry", b"{}") is None


def test_cmd_validation():
    with TestClient(main.app) as c:
        assert c.post("/api/cmd/rec01", json={}).status_code == 400
        assert c.post("/api/cmd/rec01", json={"interval_s": 1}).status_code == 422
        assert c.post("/api/cmd/rec01", json={"led": True}).status_code == 503  # sem MQTT nos testes


def test_health_reports_ip_family():
    with TestClient(main.app) as c:
        h = c.get("/api/health").json()
        assert h["ok"] is True and "ip" in h and h["ip"] is None   # MQTT desligado nos testes
