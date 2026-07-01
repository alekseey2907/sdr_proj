import requests
import random
import time
import math
from datetime import datetime

# Конфигурация
API_URL = "http://localhost:8000/api/v1/telemetry"

# Устройства
DEVICE_DRONE = "DRONE-HUNTER-01"   # Наш SDR детектор
DEVICE_MOTOR = "FACTORY-MOTOR-04" # Датчик на заводе

print("🚀 Запускаю симуляцию данных для Grafana...")
print(f"Target: {API_URL}")
print("-" * 50)

def generate_drone_data(t):
    # Симуляция приближения дрона (волна синуса + шум)
    # Используем поля IoT схемы для хранения RF данных:
    # velocity_rms_mm_s -> Уровень сигнала (0-100%)
    # dominant_freq_hz  -> Частота обнаружения (например, гуляет вокруг 915 МГц)
    
    signal_wave = (math.sin(t * 0.1) + 1) * 40 # База 0..80
    noise = random.uniform(-5, 5)
    rf_level = max(0, signal_wave + noise)
    
    is_alert = rf_level > 60
    status = "CRITICAL" if is_alert else "OK"
    
    return {
        "device_id": DEVICE_DRONE,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "metrics": {
            "velocity_rms_mm_s": round(rf_level, 2),  # MAPPED: RF Signal Strength
            "accel_peak_g": round(rf_level / 10, 2), # MAPPED: Signal Quality
            "crest_factor": round(random.uniform(1.2, 3.5), 2),
            "temperature_c": round(45 + random.uniform(-2, 2), 1),
            "dominant_freq_hz": round(915 + random.uniform(-2, 2), 1) # Mhz
        },
        "spectrum": {
            "bins": [random.uniform(0, rf_level) for _ in range(8)]
        }
    }

def generate_motor_data(t):
    # Симуляция двигателя (Вибрация)
    # Нормальная работа с редкими всплесками
    
    base_vib = 2.5
    if random.random() > 0.9: # 10% шанс удара/сбоя
        base_vib += random.uniform(5, 10)
    
    noise = random.uniform(-0.5, 0.5)
    vib_rms = base_vib + noise
    
    status = "WARNING" if vib_rms > 6.0 else "OK"
    
    return {
        "device_id": DEVICE_MOTOR,
        "timestamp": datetime.utcnow().isoformat(),
        "status": status,
        "metrics": {
            "velocity_rms_mm_s": round(vib_rms, 2), # Реальная вибрация
            "accel_peak_g": round(vib_rms * 1.41, 2),
            "crest_factor": round(random.uniform(2.5, 4.0), 2),
            "temperature_c": round(60 + t * 0.01 + random.uniform(-1, 1), 1),
            "dominant_freq_hz": 50.0 # 50 Гц сеть
        },
        "spectrum": {
            "bins": [random.uniform(0, 10) for _ in range(8)]
        }
    }

t = 0
try:
    for _ in range(60): # Генерируем данные 60 секунд
        # 1. Отправляем данные ДРОНА
        payload_drone = generate_drone_data(t)
        try:
            r = requests.post(API_URL, json=payload_drone)
            if r.status_code == 200:
                print(f"📡 [DRONE] Signal: {payload_drone['metrics']['velocity_rms_mm_s']}% | Freq: {payload_drone['metrics']['dominant_freq_hz']} MHz")
            else:
                print(f"❌ Error: {r.text}")
        except Exception as e:
            print(f"❌ Connection Failed: {e}")

        # 2. Отправляем данные ЗАВОДА
        payload_motor = generate_motor_data(t)
        try:
            r = requests.post(API_URL, json=payload_motor, timeout=1) # Fast timeout
            if r.status_code == 200:
                print(f"🏭 [FACTORY] Vib: {payload_motor['metrics']['velocity_rms_mm_s']} mm/s | Temp: {payload_motor['metrics']['temperature_c']} C")
        except:
            pass
            
        t += 1
        time.sleep(1.0) # Отправка каждую секунду

except KeyboardInterrupt:
    print("\n🛑 Симуляция остановлена")
