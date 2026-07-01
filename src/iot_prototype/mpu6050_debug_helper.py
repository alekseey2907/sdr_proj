import numpy as np
import matplotlib.pyplot as plt

def simulate_mpu6050_issues():
    # Симуляция 1 секунды данных (1000 Гц)
    t = np.linspace(0, 1, 1000)
    
    # 1. Идеальный сигнал (вибрация 50 Гц)
    ideal_signal = 0.5 * np.sin(2 * np.pi * 50 * t)
    
    # 2. Проблема: Механический шум (High Frequency Noise)
    # MPU6050 очень чувствителен. Если он плохо приклеен, он ловит "звон" корпуса.
    mech_noise = 0.2 * np.sin(2 * np.pi * 800 * t) + 0.1 * np.random.normal(0, 1, 1000)

    # 3. Проблема: Дрейф нуля (DC Bias / Gravity Leakage)
    # Если калибровка сбилась, ось Z показывает не 0, а 0.8g
    dc_bias = 0.8  
    
    # 4. Проблема: Алиасинг (Aliasing)
    # Если частота выборки 1000 Гц, а мотор вибрирует на 600 Гц + гармоники,
    # мы увидим "призраков" на низких частотах.
    
    # Итоговый грязный сигнал
    raw_signal = ideal_signal + mech_noise + dc_bias
    
    return t, raw_signal, ideal_signal

def calibration_tips():
    return """
    === ЧЕК-ЛИСТ ГРЯЗНЫХ ДАННЫХ MPU6050 ===
    
    1. ШУМ В ПОКОЕ?
       - MPU6050 шумит сам по себе (+- 0.05g).
       - РЕШЕНИЕ: Digital Low Pass Filter (DLPF) внутри чипа.
       - Установи регистр CONFIG (0x1A) в 0x03 (Bandwidth 42Hz). Это железо, не софт!
       
    2. ДРЕЙФ ПРИ ВИБРАЦИИ?
       - Датчик "сходит с ума" при сильной тряске.
       - РЕШЕНИЕ: Увеличить диапазон шкалы.
       - Регистр GYRO_CONFIG / ACCEL_CONFIG.
       - Поставь шкалу +-4g или +-8g. На +-2g он может клипповать (обрезать верхушки).
       
    3. ФАНТОМНЫЕ ПИКИ (Aliasing)?
       - Видишь частоту 10 Гц, которой нет?
       - Это алиасинг. Ты опрашиваешь медленнее, чем он вибрирует.
       - РЕШЕНИЕ: Поднять Sample Rate или включить DLPF жестче.
    """

if __name__ == "__main__":
    t, raw, ideal = simulate_mpu6050_issues()
    print(calibration_tips())
