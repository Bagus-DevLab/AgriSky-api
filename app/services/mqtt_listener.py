import json
import ssl  # <--- Tambahan Library untuk SSL
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
            print(f"[MQTT] Connected to {MQTT_BROKER}!")
            client.subscribe(MQTT_TOPIC)
        else:
            print(f"[MQTT] Failed to connect, return code {rc}")

    def on_message(client, userdata, msg):
        try:
            payload = msg.payload.decode()
            print(f"[MQTT] Received: {payload}")
            sensor_data = json.loads(payload)

            # 1. Ambil Data BMKG
            bmkg_data = bmkg_service.get_data()

            # 2. Analisis ML
            clean_result = analyzer.process_data(sensor_data, bmkg_data)

            # 3. Simpan DB
            save_weather_log(clean_result)

        except Exception as e:
            print(f"[Processing Error] {e}")

    # Setup Client ID (Randomized agar tidak tabrakan)
    client_id = f'python-mqtt-{threading.get_ident()}'
    client = mqtt_client.Client(client_id)

    # --- SETTING AUTH & SSL (BARU) ---
    # 1. Set Username & Password
    client.username_pw_set(MQTT_USER, MQTT_PASS)

    # 2. Set SSL jika Port 8883
    if MQTT_PORT == 8883:
        # Menggunakan konteks SSL default tapi mematikan verifikasi sertifikat
        # agar tidak ribet dengan file .crt (Sama seperti setInsecure di ESP32)
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message
    
    # Connect
    try:
        client.connect(MQTT_BROKER, MQTT_PORT)
    except Exception as e:
        print(f"[MQTT Connection Error] {e}")
        
    return client

def start_mqtt_loop():
    client = connect_mqtt()
    # Gunakan loop_forever di dalam thread agar auto-reconnect handle otomatis
    if client:
        client.loop_forever()