import os


DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'), # 'db' adalah nama service di docker-compose
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASS', 'rootpassword'),
    'database': os.getenv('DB_NAME', 'iot_weather_db')
}

# --- KONFIGURASI MQTT (EMQX Cloud) ---
MQTT_BROKER = os.getenv('MQTT_BROKER', 'k2519aa6.ala.asia-southeast1.emqxsl.com')
MQTT_PORT = int(os.getenv('MQTT_PORT', 8883))
MQTT_USER = os.getenv('MQTT_USER', 'PCB01')
MQTT_PASS = os.getenv('MQTT_PASS', '5ywnMzsVX4Ss9vH')

# Topik Tunggal (Sesuai kode ESP32 terbaru)
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'pcb01/status/weather')

# --- KONFIGURASI API ---
# Cache BMKG (Detik) - Update tiap 1 jam
BMKG_CACHE_TIMEOUT = 3600