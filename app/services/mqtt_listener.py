import json
import ssl
import threading
from paho.mqtt import client as mqtt_client
from app.config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_USER, MQTT_PASS
from app.services.bmkg_service import BMKGService
from app.services.ml_engine import WeatherAnalyzer
from app.database import save_weather_log

# Inisialisasi Service
bmkg_service = BMKGService()
analyzer = WeatherAnalyzer()

def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print(f"[MQTT] Connected to {MQTT_BROKER}")
            client.subscribe(MQTT_TOPIC)
            print(f"[MQTT] Subscribed to {MQTT_TOPIC}")
        else:
            print(f"[MQTT] Failed to connect, return code {rc}")

    def on_message(client, userdata, msg):
        try:
            payload_str = msg.payload.decode()
            print(f"[MQTT IN] {payload_str}")
            
            # 1. Parsing JSON dari ESP32
            sensor_data = json.loads(payload_str)

            # 2. Ambil Data BMKG (Mockup/Real API)
            bmkg_data = bmkg_service.get_data()

            # 3. Proses Analisis (ML Engine)
            clean_result = analyzer.process_data(sensor_data, bmkg_data)

            # 4. Simpan ke Database MySQL
            save_weather_log(clean_result)

        except json.JSONDecodeError:
            print("[Error] Format JSON dari ESP32 salah!")
        except Exception as e:
            print(f"[Processing Error] {e}")

    # Setup Client
    client_id = f'python-docker-{threading.get_ident()}'
    client = mqtt_client.Client(client_id)

    # Authentication
    client.username_pw_set(MQTT_USER, MQTT_PASS)

    # SSL Config untuk Port 8883
    if MQTT_PORT == 8883:
        client.tls_set(cert_reqs=ssl.CERT_NONE) # Tidak perlu file CA
        client.tls_insecure_set(True)           # Bypass hostname check

    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
    except Exception as e:
        print(f"[MQTT Connection Error] {e}")

    return client

def start_mqtt_loop():
    client = connect_mqtt()
    if client:
        client.loop_forever()