"""AnteceDengue – backend: ponte MQTT -> SQLite -> API REST/WebSocket.

Uso local:  uvicorn main:app --reload            (IPv6: uvicorn main:app --host ::)
IPv6:       MQTT_HOST pode ser um endereço IPv6 literal (ex.: ::1) ou um nome com registro AAAA.
Variáveis:  MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASS, DB_PATH, RAIN_ALERT_MM, TEMP_ALERT_C
"""
import asyncio
import json
import os
import socket
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
DB_PATH = os.getenv("DB_PATH", "antecedengue.db")
ROOT = "antecedengue/v1"
RAIN_ALERT_MM = float(os.getenv("RAIN_ALERT_MM", "10"))  # chuva acumulada no intervalo
TEMP_ALERT_C = float(os.getenv("TEMP_ALERT_C", "35"))
FRONTEND = Path(os.getenv("FRONTEND_DIR", Path(__file__).parent.parent / "frontend"))

_db_lock = threading.Lock()
_db = None
_clients: set = set()
_loop = None
_mqtt = None
_status: dict = {}  # station_id -> "online"/"offline"


def init_db(path=None):
    global _db
    _db = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    _db.row_factory = sqlite3.Row
    _db.executescript(
        """
        CREATE TABLE IF NOT EXISTS telemetry(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          station_id TEXT NOT NULL, ts INTEGER NOT NULL, recv_ts INTEGER NOT NULL,
          temperature_c REAL, relative_humidity REAL, rainfall_mm REAL,
          battery_voltage REAL, latitude REAL, longitude REAL, alert INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS ix_tel ON telemetry(station_id, ts);
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, station_id TEXT, kind TEXT, detail TEXT);
        """
    )
    _db.commit()


def compute_alert(d: dict) -> list:
    reasons = []
    if (d.get("rainfall_mm") or 0) >= RAIN_ALERT_MM:
        reasons.append("chuva")
    if (d.get("temperature_c") or 0) >= TEMP_ALERT_C:
        reasons.append("calor")
    return reasons


def log_event(station, kind, detail=""):
    with _db_lock:
        _db.execute("INSERT INTO events(ts,station_id,kind,detail) VALUES(?,?,?,?)",
                    (int(time.time()), station, kind, detail))
        _db.commit()


def handle_message(topic: str, payload: bytes):
    """Processa uma mensagem MQTT. Retorna dict para broadcast ou None."""
    parts = topic.split("/")
    if len(parts) != 4 or "/".join(parts[:2]) != ROOT:
        return None
    station, kind = parts[2], parts[3]
    text = payload.decode(errors="replace")
    if kind == "status":
        st = text.strip().strip('"').lower()
        if st in ("online", "offline"):
            _status[station] = st
            log_event(station, "status", st)
            return {"type": "status", "station_id": station, "status": st}
        return None
    if kind == "ack":
        log_event(station, "ack", text)
        return {"type": "ack", "station_id": station, "data": text}
    if kind != "telemetry":
        return None
    try:
        d = json.loads(text)
        if not isinstance(d, dict):
            raise ValueError
    except ValueError:
        log_event(station, "bad_payload", text[:200])
        return None
    reasons = compute_alert(d)
    now = int(time.time())
    row = (station, int(d.get("timestamp") or now), now,
           d.get("temperature_c"), d.get("relative_humidity"), d.get("rainfall_mm"),
           d.get("battery_voltage"), d.get("latitude"), d.get("longitude"), 1 if reasons else 0)
    with _db_lock:
        _db.execute("INSERT INTO telemetry(station_id,ts,recv_ts,temperature_c,relative_humidity,"
                    "rainfall_mm,battery_voltage,latitude,longitude,alert) VALUES(?,?,?,?,?,?,?,?,?,?)", row)
        _db.commit()
    _status.setdefault(station, "online")
    if reasons:
        log_event(station, "alert", ",".join(reasons))
    return {"type": "telemetry", "station_id": station, "alert": reasons, **d}


def _broadcast(msg):
    if not msg or _loop is None:
        return
    for ws in list(_clients):
        asyncio.run_coroutine_threadsafe(_safe_send(ws, msg), _loop)


async def _safe_send(ws, msg):
    try:
        await ws.send_json(msg)
    except Exception:
        _clients.discard(ws)


def _on_connect(c, userdata, flags, rc, props=None):
    c.subscribe([(f"{ROOT}/+/telemetry", 1), (f"{ROOT}/+/status", 1), (f"{ROOT}/+/ack", 1)])


def _on_message(c, userdata, msg):
    try:
        _broadcast(handle_message(msg.topic, msg.payload))
    except Exception as e:  # nunca derrubar a thread MQTT
        print("erro handle_message:", e)


def start_mqtt():
    global _mqtt
    _mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="antecedengue-backend")
    if MQTT_USER:
        _mqtt.username_pw_set(MQTT_USER, MQTT_PASS)
    _mqtt.on_connect = _on_connect
    _mqtt.on_message = _on_message
    _mqtt.reconnect_delay_set(1, 30)
    _mqtt.connect_async(MQTT_HOST, MQTT_PORT, 30)
    _mqtt.loop_start()


@asynccontextmanager
async def lifespan(app):
    global _loop
    _loop = asyncio.get_running_loop()
    if _db is None:
        init_db()
    if os.getenv("DISABLE_MQTT") != "1":
        start_mqtt()
    yield
    if _mqtt:
        _mqtt.loop_stop()


app = FastAPI(title="AnteceDengue API", lifespan=lifespan)


class Cmd(BaseModel):
    led: bool | None = None
    interval_s: int | None = Field(default=None, ge=2, le=3600)
    rain_alert_mm: float | None = Field(default=None, ge=0, le=500)


def broker_ip_family():
    """Versão de IP da conexão ativa com o broker ('IPv6', 'IPv4' ou None se desconectado)."""
    try:
        sock = _mqtt.socket() if _mqtt else None
        if sock is None:
            return None
        return "IPv6" if sock.family == socket.AF_INET6 else "IPv4"
    except Exception:
        return None


@app.get("/api/health")
def health():
    return {"ok": True, "mqtt": bool(_mqtt and _mqtt.is_connected()), "ip": broker_ip_family()}


@app.get("/api/stations")
def stations():
    with _db_lock:
        rows = _db.execute(
            "SELECT t.* FROM telemetry t JOIN (SELECT station_id, MAX(id) mid FROM telemetry "
            "GROUP BY station_id) m ON t.id=m.mid").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["status"] = _status.get(d["station_id"], "unknown")
        out.append(d)
    return out


@app.get("/api/telemetry")
def telemetry(station: str, limit: int = 200):
    limit = max(1, min(limit, 5000))
    with _db_lock:
        rows = _db.execute("SELECT * FROM telemetry WHERE station_id=? ORDER BY id DESC LIMIT ?",
                           (station, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]


@app.get("/api/events")
def events(limit: int = 50):
    with _db_lock:
        rows = _db.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (min(limit, 500),)).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/cmd/{station}")
def send_cmd(station: str, cmd: Cmd):
    body = cmd.model_dump(exclude_none=True)
    if not body:
        raise HTTPException(400, "comando vazio")
    if _mqtt is None:
        raise HTTPException(503, "MQTT indisponível")
    _mqtt.publish(f"{ROOT}/{station}/cmd", json.dumps(body), qos=1)
    log_event(station, "cmd", json.dumps(body))
    return {"sent": body}


@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    _clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


if FRONTEND.exists():
    @app.get("/")
    def index():
        return FileResponse(FRONTEND / "index.html")

    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
