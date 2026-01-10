import requests
import time
import json
from datetime import datetime
from app.config import BMKG_CONFIG

class BMKGService:
    def __init__(self):
        self.cache = {
            'temp': 30.0, # Nilai Default (Fallback)
            'wind': 5.0,
            'last_update': 0
        }

    def get_data(self):
        now = time.time()
        
        # Cek apakah cache sudah kadaluarsa?
        if now - self.cache['last_update'] > BMKG_CONFIG['fetch_interval']:
            self._fetch_from_api()
            
        return self.cache

    def _fetch_from_api(self):
        try:
            print("[BMKG] Fetching Real Data from API...")
            
            params = {'adm4': BMKG_CONFIG['location_code']}
            response = requests.get(BMKG_CONFIG['api_url'], params=params, timeout=10)
            
            if response.status_code == 200:
                data_json = response.json()
                
                # --- DEBUGGING (Melihat struktur asli di logs jika error lagi) ---
                # print(f"[DEBUG JSON] {json.dumps(data_json['data'][0]['cuaca'], indent=1)}")

                # Ambil list cuaca
                raw_cuaca = data_json['data'][0]['cuaca']
                
                # --- FIX: FLATTENING LIST ---
                # Masalah 'list has no attribute get' terjadi karena datanya nested (List di dalam List)
                # Kita ratakan menjadi satu list panjang berisi dictionary semua
                flat_cuaca_list = []
                
                for item in raw_cuaca:
                    if isinstance(item, list):
                        # Jika item adalah list (per hari), masukkan isinya ke list utama
                        flat_cuaca_list.extend(item)
                    else:
                        # Jika item sudah dictionary, langsung masukkan
                        flat_cuaca_list.append(item)
                
                # Cari data terdekat dari list yang sudah diratakan
                closest_data = self._find_closest_forecast(flat_cuaca_list)
                
                if closest_data:
                    # 't' = Temperature, 'ws' = Wind Speed
                    self.cache['temp'] = float(closest_data.get('t', 30))
                    self.cache['wind'] = float(closest_data.get('ws', 5))
                    self.cache['last_update'] = time.time()
                    
                    print(f"[BMKG] Update Sukses! Temp: {self.cache['temp']}C, Wind: {self.cache['wind']} km/h")
                else:
                    print("[BMKG] Tidak menemukan data waktu yang cocok.")
            else:
                print(f"[BMKG] Gagal Fetch API. Status: {response.status_code}")
                
        except Exception as e:
            print(f"[BMKG Error] Logic Error: {e}")

    def _find_closest_forecast(self, weather_list):
        """Mencari prediksi cuaca yang jamnya paling dekat dengan sekarang"""
        now = datetime.now()
        closest_entry = None
        min_diff = float('inf') 

        for entry in weather_list:
            # Validasi: Pastikan entry adalah dictionary
            if not isinstance(entry, dict):
                continue

            # Coba ambil datetime (kadang key-nya beda)
            time_str = entry.get('local_datetime', entry.get('datetime'))
            
            if time_str:
                try:
                    # Format API BMKG: "2024-01-10 12:00:00"
                    entry_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                    
                    # Hitung selisih waktu
                    diff = abs((now - entry_time).total_seconds())
                    
                    if diff < min_diff:
                        min_diff = diff
                        closest_entry = entry
                except ValueError:
                    continue
        
        return closest_entry