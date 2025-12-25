import os, json, ssl, threading
from datetime import datetime
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

load_dotenv()

# MQTT Config
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID")

# PostgreSQL Config
DATABASE_URL = os.getenv("DATABASE_URL")
# Format: postgresql://username:password@host:port/database

# Topics dari ESP32
TOPIC_ANEMO = "pcb01/status/anemometer"
TOPIC_RAIN = "pcb01/status/rain"
TOPIC_DHT = "pcb01/status/dht"

app = FastAPI(title="Weather Station API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database Setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class AnemometerData(Base):
    __tablename__ = "anemometer_data"
    
    id = Column(Integer, primary_key=True, index=True)
    rpm = Column(Float)
    wind_speed = Column(Float)
    unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class RainData(Base):
    __tablename__ = "rain_data"
    
    id = Column(Integer, primary_key=True, index=True)
    analog_value = Column(Integer)
    status = Column(String)
    moisture = Column(Integer)
    unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class DHTData(Base):
    __tablename__ = "dht_data"
    
    id = Column(Integer, primary_key=True, index=True)
    temperature = Column(Float)
    humidity = Column(Float)
    temp_unit = Column(String)
    hum_unit = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

# Create tables
Base.metadata.create_all(bind=engine)

# In-memory data storage (untuk realtime)
anemo_data = {
    "rpm": 0.0,
    "wind": 0.0,
    "unit": "m/s",
    "last_update": None
}

rain_data = {
    "analog": 0,
    "status": "unknown",
    "moisture": 0,
    "unit": "%",
    "last_update": None
}

dht_data = {
    "temperature": 0.0,
    "humidity": 0.0,
    "temp_unit": "°C",
    "hum_unit": "%",
    "last_update": None
}

# Helper function untuk save ke database
def save_to_db(data_type: str, payload: dict):
    db = SessionLocal()
    try:
        if data_type == "anemometer":
            record = AnemometerData(
                rpm=payload.get("rpm"),
                wind_speed=payload.get("wind"),
                unit=payload.get("unit")
            )
        elif data_type == "rain":
            record = RainData(
                analog_value=payload.get("analog"),
                status=payload.get("status"),
                moisture=payload.get("moisture"),
                unit=payload.get("unit")
            )
        elif data_type == "dht":
            record = DHTData(
                temperature=payload.get("temperature"),
                humidity=payload.get("humidity"),
                temp_unit=payload.get("temp_unit"),
                hum_unit=payload.get("hum_unit")
            )
        
        db.add(record)
        db.commit()
        print(f"💾 Saved {data_type} to database")
    except Exception as e:
        print(f"❌ Database error: {e}")
        db.rollback()
    finally:
        db.close()

# MQTT Setup
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID)
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

mqtt_client.tls_set(
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLS_CLIENT,
)

def on_connect(client, userdata, flags, rc):
    print(f"✅ MQTT Connected with code: {rc}")
    client.subscribe(TOPIC_ANEMO)
    client.subscribe(TOPIC_RAIN)
    client.subscribe(TOPIC_DHT)
    print(f"📡 Subscribed to all topics")

def on_message(client, userdata, msg):
    global anemo_data, rain_data, dht_data
    
    try:
        payload = json.loads(msg.payload.decode())
        now = datetime.now().isoformat()
        
        if msg.topic == TOPIC_ANEMO:
            anemo_data.update(payload)
            anemo_data["last_update"] = now
            save_to_db("anemometer", payload)
            print(f"💨 Anemometer: {payload}")
            
        elif msg.topic == TOPIC_RAIN:
            rain_data.update(payload)
            rain_data["last_update"] = now
            save_to_db("rain", payload)
            print(f"🌧️ Rain: {payload}")
            
        elif msg.topic == TOPIC_DHT:
            dht_data.update(payload)
            dht_data["last_update"] = now
            save_to_db("dht", payload)
            print(f"🌡️ DHT: {payload}")
            
    except Exception as e:
        print(f"❌ Error processing message: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def mqtt_loop():
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"❌ MQTT Connection Error: {e}")

threading.Thread(target=mqtt_loop, daemon=True).start()

# API Endpoints - Realtime Data

@app.get("/")
def root():
    return {
        "message": "Weather Station API with Database",
        "endpoints": {
            "realtime": ["/anemometer", "/rain", "/dht", "/weather"],
            "history": ["/history/anemometer", "/history/rain", "/history/dht", "/history/all"],
            "stats": ["/stats/anemometer", "/stats/rain", "/stats/dht"]
        }
    }

@app.get("/anemometer")
def read_anemometer():
    """Get current anemometer data"""
    if anemo_data["wind"] == 0 and anemo_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data anemometer")
    return anemo_data

@app.get("/rain")
def read_rain():
    """Get current rain sensor data"""
    if rain_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data rain sensor")
    return rain_data

@app.get("/dht")
def read_dht():
    """Get current DHT11 data"""
    if dht_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data DHT11")
    return dht_data

@app.get("/weather")
def read_all_weather():
    """Get all current weather data"""
    return {
        "wind": {
            "speed": anemo_data["wind"],
            "rpm": anemo_data["rpm"],
            "unit": anemo_data["unit"],
            "last_update": anemo_data["last_update"]
        },
        "rain": {
            "status": rain_data["status"],
            "moisture": rain_data["moisture"],
            "analog_value": rain_data["analog"],
            "unit": rain_data["unit"],
            "last_update": rain_data["last_update"]
        },
        "temperature": {
            "value": dht_data["temperature"],
            "unit": dht_data["temp_unit"],
            "last_update": dht_data["last_update"]
        },
        "humidity": {
            "value": dht_data["humidity"],
            "unit": dht_data["hum_unit"],
            "last_update": dht_data["last_update"]
        }
    }

# API Endpoints - Historical Data

@app.get("/history/anemometer")
def get_anemometer_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get historical anemometer data"""
    db = SessionLocal()
    try:
        records = db.query(AnemometerData)\
            .order_by(AnemometerData.timestamp.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()
        
        return {
            "total": db.query(AnemometerData).count(),
            "data": [
                {
                    "id": r.id,
                    "rpm": r.rpm,
                    "wind_speed": r.wind_speed,
                    "unit": r.unit,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in records
            ]
        }
    finally:
        db.close()

@app.get("/history/rain")
def get_rain_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get historical rain data"""
    db = SessionLocal()
    try:
        records = db.query(RainData)\
            .order_by(RainData.timestamp.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()
        
        return {
            "total": db.query(RainData).count(),
            "data": [
                {
                    "id": r.id,
                    "analog_value": r.analog_value,
                    "status": r.status,
                    "moisture": r.moisture,
                    "unit": r.unit,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in records
            ]
        }
    finally:
        db.close()

@app.get("/history/dht")
def get_dht_history(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """Get historical temperature & humidity data"""
    db = SessionLocal()
    try:
        records = db.query(DHTData)\
            .order_by(DHTData.timestamp.desc())\
            .offset(offset)\
            .limit(limit)\
            .all()
        
        return {
            "total": db.query(DHTData).count(),
            "data": [
                {
                    "id": r.id,
                    "temperature": r.temperature,
                    "humidity": r.humidity,
                    "temp_unit": r.temp_unit,
                    "hum_unit": r.hum_unit,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in records
            ]
        }
    finally:
        db.close()

@app.get("/stats/anemometer")
def get_anemometer_stats():
    """Get anemometer statistics"""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        stats = db.query(
            func.avg(AnemometerData.wind_speed).label('avg'),
            func.min(AnemometerData.wind_speed).label('min'),
            func.max(AnemometerData.wind_speed).label('max'),
            func.count(AnemometerData.id).label('count')
        ).first()
        
        return {
            "average_wind_speed": round(stats.avg, 2) if stats.avg else 0,
            "min_wind_speed": round(stats.min, 2) if stats.min else 0,
            "max_wind_speed": round(stats.max, 2) if stats.max else 0,
            "total_records": stats.count,
            "unit": "m/s"
        }
    finally:
        db.close()

@app.get("/stats/dht")
def get_dht_stats():
    """Get temperature & humidity statistics"""
    db = SessionLocal()
    try:
        from sqlalchemy import func
        stats = db.query(
            func.avg(DHTData.temperature).label('avg_temp'),
            func.min(DHTData.temperature).label('min_temp'),
            func.max(DHTData.temperature).label('max_temp'),
            func.avg(DHTData.humidity).label('avg_hum'),
            func.min(DHTData.humidity).label('min_hum'),
            func.max(DHTData.humidity).label('max_hum'),
            func.count(DHTData.id).label('count')
        ).first()
        
        return {
            "temperature": {
                "average": round(stats.avg_temp, 2) if stats.avg_temp else 0,
                "min": round(stats.min_temp, 2) if stats.min_temp else 0,
                "max": round(stats.max_temp, 2) if stats.max_temp else 0,
                "unit": "°C"
            },
            "humidity": {
                "average": round(stats.avg_hum, 2) if stats.avg_hum else 0,
                "min": round(stats.min_hum, 2) if stats.min_hum else 0,
                "max": round(stats.max_hum, 2) if stats.max_hum else 0,
                "unit": "%"
            },
            "total_records": stats.count
        }
    finally:
        db.close()

@app.get("/health")
def health_check():
    """Check system health"""
    db = SessionLocal()
    try:
        # Test database connection
        db.execute("SELECT 1")
        db_connected = True
    except:
        db_connected = False
    finally:
        db.close()
    
    return {
        "mqtt_connected": mqtt_client.is_connected(),
        "database_connected": db_connected,
        "sensors": {
            "anemometer": anemo_data["last_update"] is not None,
            "rain": rain_data["last_update"] is not None,
            "dht": dht_data["last_update"] is not None
        },
        "last_updates": {
            "anemometer": anemo_data["last_update"],
            "rain": rain_data["last_update"],
            "dht": dht_data["last_update"]
        }
    }