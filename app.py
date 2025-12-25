import os
import json
import ssl
import threading
import logging
from datetime import datetime
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import paho.mqtt.client as mqtt

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    DateTime,
    func,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ======================================================
# ENV & LOGGING
# ======================================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("weather-api")

# ======================================================
# CONFIG
# ======================================================
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "weather-api")
MQTT_TLS = os.getenv("MQTT_TLS", "false").lower() == "true"

DATABASE_URL = os.getenv("DATABASE_URL")

TOPIC_ANEMO = "pcb01/status/anemometer"
TOPIC_RAIN = "pcb01/status/rain"
TOPIC_DHT = "pcb01/status/dht"

# ======================================================
# FASTAPI INIT
# ======================================================
app = FastAPI(title="Weather Station API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================================================
# DATABASE
# ======================================================
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class AnemometerData(Base):
    __tablename__ = "anemometer_data"
    id = Column(Integer, primary_key=True)
    rpm = Column(Float)
    wind_speed = Column(Float)
    unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class RainData(Base):
    __tablename__ = "rain_data"
    id = Column(Integer, primary_key=True)
    analog_value = Column(Integer)
    status = Column(String)
    moisture = Column(Integer)
    unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class DHTData(Base):
    __tablename__ = "dht_data"
    id = Column(Integer, primary_key=True)
    temperature = Column(Float)
    humidity = Column(Float)
    temp_unit = Column(String)
    hum_unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


Base.metadata.create_all(bind=engine)

# ======================================================
# SHARED REALTIME STATE (THREAD SAFE)
# ======================================================
data_lock = threading.Lock()

anemo_data: Dict = {
    "rpm": 0.0,
    "wind": 0.0,
    "unit": "m/s",
    "last_update": None,
}

rain_data: Dict = {
    "analog": 0,
    "status": "unknown",
    "moisture": 0,
    "unit": "%",
    "last_update": None,
}

dht_data: Dict = {
    "temperature": 0.0,
    "humidity": 0.0,
    "temp_unit": "°C",
    "hum_unit": "%",
    "last_update": None,
}

# ======================================================
# DATABASE HELPER
# ======================================================
def save_to_db(data_type: str, payload: dict) -> None:
    db = SessionLocal()
    try:
        if data_type == "anemometer":
            db.add(
                AnemometerData(
                    rpm=payload.get("rpm"),
                    wind_speed=payload.get("wind"),
                    unit=payload.get("unit"),
                )
            )
        elif data_type == "rain":
            db.add(
                RainData(
                    analog_value=payload.get("analog"),
                    status=payload.get("status"),
                    moisture=payload.get("moisture"),
                    unit=payload.get("unit"),
                )
            )
        elif data_type == "dht":
            db.add(
                DHTData(
                    temperature=payload.get("temperature"),
                    humidity=payload.get("humidity"),
                    temp_unit=payload.get("temp_unit"),
                    hum_unit=payload.get("hum_unit"),
                )
            )

        db.commit()
        logger.info("Saved %s data", data_type)

    except Exception as e:
        db.rollback()
        logger.error("DB error (%s): %s", data_type, e)

    finally:
        db.close()


# ======================================================
# MQTT
# ======================================================
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)

if MQTT_USER and MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

if MQTT_TLS:
    mqtt_client.tls_set(
        cert_reqs=ssl.CERT_REQUIRED,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("MQTT connected")
        client.subscribe(
            [
                (TOPIC_ANEMO, 0),
                (TOPIC_RAIN, 0),
                (TOPIC_DHT, 0),
            ]
        )
    else:
        logger.error("MQTT connection failed: %s", rc)


def on_message(client, userdata, msg):
    # // Parse payload and update shared state
    try:
        payload = json.loads(msg.payload.decode())
        now = datetime.utcnow().isoformat()

        with data_lock:
            if msg.topic == TOPIC_ANEMO:
                anemo_data.update(payload)
                anemo_data["last_update"] = now
                save_to_db("anemometer", payload)

            elif msg.topic == TOPIC_RAIN:
                rain_data.update(payload)
                rain_data["last_update"] = now
                save_to_db("rain", payload)

            elif msg.topic == TOPIC_DHT:
                dht_data.update(payload)
                dht_data["last_update"] = now
                save_to_db("dht", payload)

    except Exception as e:
        logger.error("MQTT message error: %s", e)


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


def mqtt_loop():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        logger.error("MQTT loop error: %s", e)


# ======================================================
# FASTAPI LIFECYCLE
# ======================================================
@app.on_event("startup")
def startup_event():
    logger.info("Starting MQTT thread")
    threading.Thread(target=mqtt_loop, daemon=True).start()


@app.on_event("shutdown")
def shutdown_event():
    logger.info("Stopping MQTT client")
    mqtt_client.disconnect()


# ======================================================
# API ENDPOINTS
# ======================================================
@app.get("/")
def root():
    return {"status": "Weather Station API running"}


@app.get("/anemometer")
def read_anemometer():
    if not anemo_data["last_update"]:
        raise HTTPException(503, "Belum ada data anemometer")
    return anemo_data


@app.get("/rain")
def read_rain():
    if not rain_data["last_update"]:
        raise HTTPException(503, "Belum ada data rain")
    return rain_data


@app.get("/dht")
def read_dht():
    if not dht_data["last_update"]:
        raise HTTPException(503, "Belum ada data DHT")
    return dht_data


@app.get("/health")
def health():
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    return {
        "mqtt_connected": mqtt_client.is_connected(),
        "database_connected": db_ok,
    }
