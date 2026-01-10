from sklearn.ensemble import IsolationForest
import numpy as np

class WeatherAnalyzer:
    def __init__(self):
        # Latih model dummy saat start
        self.model_temp = self._train_initial_model()

    def _train_initial_model(self):
        # Simulasi data historis: Selisih suhu normalnya kecil (0-2 derajat)
        rng = np.random.RandomState(42)
        X_train = 0.5 * rng.randn(100, 1) 
        clf = IsolationForest(random_state=42, contamination=0.1)
        clf.fit(X_train)
        return clf

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
        
        b_temp = bmkg_data.get('temp', 30.0)
        
        # Default Keputusan: Percaya Sensor
        final_temp = s_temp
        source_note = "Sensor Lokal"

        # --- A. LOGIC SUHU (Anomaly Detection) ---
        # Hitung selisih suhu sensor vs BMKG
        diff = np.array([[s_temp - b_temp]])
        
        # Prediksi: -1 artinya Anomali (Beda terlalu jauh)
        if self.model_temp.predict(diff)[0] == -1:
            final_temp = b_temp
            source_note = "Fallback BMKG (Sensor Suhu Anomali)"

        # --- B. LOGIC HUJAN (Rule Based) ---
        # 0% = Kering, 100% = Basah Kuyup
        # Kita set threshold misal > 60% dianggap hujan
        final_rain = "Cerah"
        
        if s_rain_pct > 60:
            final_rain = "Hujan"
            # Validasi Fisika: Gak mungkin hujan kalau kelembapan udara kering (<50%)
            if s_hum < 50:
                final_rain = "Cerah (Sensor Hujan False Alarm)"
                source_note += " + Koreksi Hujan"
        
        elif s_rain_pct > 30:
            final_rain = "Gerimis/Mendung"

        # --- C. Return Data Rapih ---
        return {
            's_temp': s_temp, 's_hum': s_hum, 's_wind': s_wind, 
            's_rpm': sensor_data.get('rpm', 0),
            's_rain_raw': sensor_data.get('rain_raw', 4095), 
            's_rain_pct': s_rain_pct,
            
            'b_temp': b_temp, 'b_wind': bmkg_data.get('wind', 0),
            
            'final_temp': final_temp, 
            'final_wind': s_wind, # Angin biasanya sangat lokal, percaya sensor
            'final_rain': final_rain,
            'source': source_note
        }