from sklearn.ensemble import IsolationForest
import numpy as np

class WeatherAnalyzer:
    def __init__(self):
        # Kita butuh DUA model terpisah
        # 1. Model untuk Suhu
        # 2. Model untuk Angin
        self.model_temp, self.model_wind = self._train_initial_models()

    def _train_initial_models(self):
        rng = np.random.RandomState(42)
        
        # --- TRAIN MODEL SUHU ---
        # Data dummy: Selisih suhu biasanya 0 - 2 derajat
        X_train_temp = 0.5 * rng.randn(100, 1) 
        clf_temp = IsolationForest(random_state=42, contamination=0.1)
        clf_temp.fit(X_train_temp)

        # --- TRAIN MODEL ANGIN ---
        # Data dummy: Selisih angin bisa lebih besar (karena lokasi sensor vs BMKG jauh)
        # Kita buat variasi data latihnya lebih lebar (misal selisih 0 - 5 m/s masih wajar)
        X_train_wind = 1.5 * rng.randn(100, 1) 
        clf_wind = IsolationForest(random_state=42, contamination=0.1)
        clf_wind.fit(X_train_wind)

        return clf_temp, clf_wind

    def process_data(self, sensor_data, bmkg_data):
        """
        Input: 
            sensor_data = {'temp': 30, 'hum': 60, 'wind': 5.0, 'rain_pct': 80, ...}
            bmkg_data   = {'temp': 29, 'wind': 4.0}
        """
        
        # 1. Parsing Data Masuk
        s_temp = float(sensor_data.get('temp', 0))
        s_hum = float(sensor_data.get('hum', 0))
        s_wind = float(sensor_data.get('wind', 0))
        s_rain_pct = int(sensor_data.get('rain_pct', 0)) # 0-100%
        
        b_temp = bmkg_data.get('temp', s_temp) # Fallback ke sensor jika BMKG mati
        b_wind = bmkg_data.get('wind', s_wind)
        
        # --- Variable Penampung Keputusan ---
        final_temp = s_temp
        final_wind = s_wind
        final_rain = "Cerah"
        notes = [] # Untuk menampung alasan (Decision Source)

        # =========================================
        # 1. ANALISIS SUHU (Machine Learning)
        # =========================================
        diff_temp = np.array([[s_temp - b_temp]])
        if self.model_temp.predict(diff_temp)[0] == -1:
            # Jika ML bilang anomali (beda jauh), percaya BMKG
            final_temp = b_temp
            notes.append("Suhu: Fallback BMKG (Sensor Anomali)")
        else:
            notes.append("Suhu: Sensor Lokal")

        # =========================================
        # 2. ANALISIS ANGIN (Machine Learning)
        # =========================================
        # Angin itu tricky. Kalau sensor kita di bawah pohon/tembok, anginnya 0.
        # Kalau BMKG di menara tinggi, anginnya 20km/h.
        # Jadi kita set: Jika sensor ada nilai, pakai sensor. 
        # TAPI jika selisihnya ekstrem (Sensor badai 50km/h tapi BMKG kalem 5km/h), itu error.
        
        diff_wind = np.array([[s_wind - b_wind]])
        
        # Cek Anomali Angin
        if self.model_wind.predict(diff_wind)[0] == -1:
            # Terjadi perbedaan ekstrem
            # Kasus: Sensor rusak (reading 100m/s) atau tertutup total
            final_wind = b_wind
            notes.append("Angin: Fallback BMKG (Selisih Ekstrem)")
        else:
            final_wind = s_wind
            notes.append("Angin: Sensor Lokal")

        # =========================================
        # 3. ANALISIS HUJAN (Correlation Logic)
        # =========================================
        # ML Rule: Hujan Valid HANYA JIKA Kelembapan Tinggi.
        # Threshold: Rain Pct > 30% dianggap mulai basah.
        
        is_sensor_raining = s_rain_pct > 30
        
        if is_sensor_raining:
            # Cek Korelasi Fisika: Apakah Humidity mendukung hujan?
            # Biasanya hujan terjadi saat Humidity > 70%
            if s_hum > 60: 
                final_rain = "Hujan"
                notes.append("Hujan: Valid (Sensor + Humid)")
            else:
                # Sensor hujan basah, tapi udara kering kerontang (<60%)
                # Kesimpulan: False Alarm (Mungkin ada yang nyiram air ke sensor)
                final_rain = "Cerah"
                notes.append("Hujan: False Alarm (Udara Kering)")
        else:
            # Sensor Hujan Kering
            final_rain = "Cerah"
            if s_hum > 95:
                 notes.append("Status: Mendung/Lembap")
            else:
                 notes.append("Status: Cerah")

        # =========================================
        # 4. FINALISASI
        # =========================================
        
        return {
            's_temp': s_temp, 's_hum': s_hum, 's_wind': s_wind, 
            's_rpm': sensor_data.get('rpm', 0),
            's_rain_raw': sensor_data.get('rain_raw', 4095), 
            's_rain_pct': s_rain_pct,
            
            'b_temp': b_temp, 'b_wind': b_wind,
            
            'final_temp': final_temp, 
            'final_wind': final_wind,
            'final_rain': final_rain,
            'source': " | ".join(notes) # Gabungkan semua catatan
        }