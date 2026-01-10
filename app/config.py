import os

# Database Config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'db'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASS', 'rootpassword'),
    'database': os.getenv('DB_NAME', 'iot_weather_db')
}

# MQTT Config
MQTT_BROKER = os.getenv('MQTT_BROKER', 'k2519aa6.ala.asia-southeast1.emqxsl.com')
MQTT_PORT = int(os.getenv('MQTT_PORT', 8883))
MQTT_USER = os.getenv('MQTT_USER', 'PCB01')
MQTT_PASS = os.getenv('MQTT_PASS', '5ywnMzsVX4Ss9vH')
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'pcb01/status/weather')

# --- BMKG API CONFIGURATION (NEW) ---
BMKG_CONFIG = {
    'api_url': "https://api.bmkg.go.id/publik/prakiraan-cuaca",
    'location_code': "31.71.01.1001",  # Kode Wilayah (Palembang area)
    'fetch_interval': 10800  # 3 Jam sekali update
}