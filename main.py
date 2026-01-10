import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.services.mqtt_listener import start_mqtt_loop
from app.database import init_db
from app.database import get_latest_weather, get_weather_history

# --- LIFESPAN (Gaya Baru Pengganti Startup/Shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- BAGIAN STARTUP (Dijalankan saat app nyala) ---
    print("--- STARTING WEATHER AI SERVICE (LIFESPAN) ---")
    
    # 1. Init Database
    try:
        init_db()
    except Exception as e:
        print(f"Warning: Database belum siap ({e})")

    # 2. Jalankan MQTT
    mqtt_thread = threading.Thread(target=start_mqtt_loop)
    mqtt_thread.daemon = True
    mqtt_thread.start()
    
    yield # <--- Titik jeda (Aplikasi berjalan disini)
    
    # --- BAGIAN SHUTDOWN (Dijalankan saat app mau mati) ---
    print("--- STOPPING SERVICE ---")
    # Disini kamu bisa taruh kode bersih-bersih jika nanti butuh
    # Contoh: disconnect_mqtt() atau close_db_pool()
    print("Service stopped gracefully.")

# Pasang lifespan ke dalam app
app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {
        "service": "IoT Weather AI", 
        "status": "Running",
        "mode": "Lifespan Context"
    }
    
    
@app.get("/api/weather/status")
def api_current_water():
    try:
        data = get_latest_weather()
        if data:
            return{
                "status": "success",
                "data": data
            }
        else:
            return{
                "status": "error",
                "message": "No weather data found."
            }
    except Exception as e:
        return{
            "status": "error",
            "message": str(e)
        }
        
@app.get("/api/weather/history")
def api_weather_history(limit: int = 5):
    """
    Mengambil data history. 
    Bisa request jumlah data, misal: /api/weather/history?limit=10
    """
    try:
        data = get_weather_history(limit)
        return {
            "status": "success",
            "count": len(data),
            "data": data
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}