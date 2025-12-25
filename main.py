import os, json, ssl, threading
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt

load_dotenv()

MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT"))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASS = os.getenv("MQTT_PASS")
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID")

# Topics dari ESP32
TOPIC_ANEMO = "pcb01/status/anemometer"
TOPIC_RAIN = "pcb01/status/rain"
TOPIC_DHT = "pcb01/status/dht"

app = FastAPI(title="Weather Station API", version="1.0.0")

# CORS middleware (opsional, untuk akses dari frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data storage
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
    print(f"📡 Subscribed to:\n  - {TOPIC_ANEMO}\n  - {TOPIC_RAIN}\n  - {TOPIC_DHT}")

def on_message(client, userdata, msg):
    global anemo_data, rain_data, dht_data
    
    try:
        payload = json.loads(msg.payload.decode())
        
        if msg.topic == TOPIC_ANEMO:
            anemo_data.update(payload)
            from datetime import datetime
            anemo_data["last_update"] = datetime.now().isoformat()
            print(f"💨 Anemometer: {payload}")
            
        elif msg.topic == TOPIC_RAIN:
            rain_data.update(payload)
            from datetime import datetime
            rain_data["last_update"] = datetime.now().isoformat()
            print(f"🌧️ Rain: {payload}")
            
        elif msg.topic == TOPIC_DHT:
            dht_data.update(payload)
            from datetime import datetime
            dht_data["last_update"] = datetime.now().isoformat()
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

# API Endpoints

@app.get("/")
def root():
    return {
        "message": "Weather Station API",
        "endpoints": [
            "/anemometer",
            "/rain",
            "/dht",
            "/temperature",
            "/humidity",
            "/weather"
        ]
    }

@app.get("/anemometer")
def read_anemometer():
    """Get anemometer (wind speed) data"""
    if anemo_data["wind"] == 0 and anemo_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data anemometer")
    return anemo_data

@app.get("/rain")
def read_rain():
    """Get rain sensor data"""
    if rain_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data rain sensor")
    return rain_data

@app.get("/dht")
def read_dht():
    """Get DHT11 (temperature & humidity) data"""
    if dht_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data DHT11")
    return dht_data

@app.get("/temperature")
def read_temperature():
    """Get temperature only"""
    if dht_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data temperature")
    return {
        "temperature": dht_data["temperature"],
        "unit": dht_data["temp_unit"],
        "last_update": dht_data["last_update"]
    }

@app.get("/humidity")
def read_humidity():
    """Get humidity only"""
    if dht_data["last_update"] is None:
        raise HTTPException(503, "Belum ada data humidity")
    return {
        "humidity": dht_data["humidity"],
        "unit": dht_data["hum_unit"],
        "last_update": dht_data["last_update"]
    }

@app.get("/weather")
def read_all_weather():
    """Get all weather data in one response"""
    if (anemo_data["last_update"] is None and 
        rain_data["last_update"] is None and 
        dht_data["last_update"] is None):
        raise HTTPException(503, "Belum ada data sensor")
    
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

@app.get("/health")
def health_check():
    """Check if sensors are sending data"""
    return {
        "mqtt_connected": mqtt_client.is_connected(),
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