import mysql.connector
import time
from app.config import DB_CONFIG

def get_db_connection():
    # Loop sederhana untuk retry koneksi jika Database belum siap saat Docker baru start
    retries = 5
    while retries > 0:
        try:
            return mysql.connector.connect(**DB_CONFIG)
        except mysql.connector.Error as err:
            print(f"[DB] Belum siap, retry dalam 5 detik... ({err})")
            time.sleep(5)
            retries -= 1
    raise Exception("[DB] Gagal connect ke Database")

def init_db():
    """Membuat tabel otomatis saat aplikasi jalan"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Query Tabel Sesuai Data ESP32 Terbaru
    sql_create = """
    CREATE TABLE IF NOT EXISTS weather_logs (
        id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
        
        -- Data RAW dari Sensor
        sensor_temp DECIMAL(5,2),
        sensor_hum DECIMAL(5,2),
        sensor_wind DECIMAL(5,2),
        sensor_rpm DECIMAL(8,2),
        sensor_rain_raw INT,
        sensor_rain_pct INT,
        
        -- Data Pembanding BMKG
        bmkg_temp DECIMAL(5,2),
        bmkg_wind DECIMAL(5,2),
        
        -- Data FINAL (Hasil Keputusan ML)
        final_temp DECIMAL(5,2),
        final_wind DECIMAL(5,2),
        final_rain_status VARCHAR(50), 
        
        -- Metadata
        decision_source VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    cursor.execute(sql_create)
    conn.commit()
    cursor.close()
    conn.close()
    print("[DB] Tabel 'weather_logs' siap/sudah ada.")

def save_weather_log(data):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
            INSERT INTO weather_logs 
            (sensor_temp, sensor_hum, sensor_wind, sensor_rpm, sensor_rain_raw, sensor_rain_pct,
             bmkg_temp, bmkg_wind, 
             final_temp, final_wind, final_rain_status, decision_source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        val = (
            data['s_temp'], data['s_hum'], data['s_wind'], data['s_rpm'], data['s_rain_raw'], data['s_rain_pct'],
            data['b_temp'], data['b_wind'],
            data['final_temp'], data['final_wind'], data['final_rain'], 
            data['source']
        )
        
        cursor.execute(sql, val)
        conn.commit()
        print(f"[DB] Data tersimpan. Status: {data['final_rain']}")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[DB Error] Gagal simpan: {e}")