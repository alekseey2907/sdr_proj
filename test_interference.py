"""
Тест помех от бытовой техники (миксер, дрель, и т.д.)

Использование:
1. Запустите скрипт: python test_interference.py
2. Когда появится "Записываю ЧИСТЫЙ спектр..." - НЕ включайте миксер
3. Дождитесь "Базовая линия записана"
4. Когда появится "ВКЛЮЧИТЕ МИКСЕР!" - включите миксер
5. Программа покажет, какие помехи он создаёт
"""
import time
import sys
from pathlib import Path

# Добавляем путь к модулям проекта
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rf_analyzer.rf.sdr_device import RTLSDRDevice
from rf_analyzer.rf.signal_processor import SignalProcessor
from rf_analyzer.core.config import DetectionConfig, DeviceConfig
from rf_analyzer.utils.interference_analyzer import InterferenceAnalyzer

def main():
    print("=" * 80)
    print("🔍 ТЕСТ ПОМЕХ ОТ БЫТОВОЙ ТЕХНИКИ")
    print("=" * 80)
    print()
    
    # Настройки
    CENTER_FREQ = 470e6  # 470 МГц (ТВ-диапазон, где обычно помехи от миксера)
    SAMPLE_RATE = 2.4e6  # 2.4 МГц
    
    print(f"Частота: {CENTER_FREQ/1e6:.1f} МГц")
    print(f"Полоса обзора: {SAMPLE_RATE/1e6:.1f} МГц ({CENTER_FREQ/1e6 - SAMPLE_RATE/2e6:.1f} - {CENTER_FREQ/1e6 + SAMPLE_RATE/2e6:.1f} МГц)")
    print()
    
    # Инициализация устройства
    print("Подключаюсь к RTL-SDR...")
    try:
        # Создаём конфигурацию устройства
        from rf_analyzer.core.config import DeviceType
        device_config = DeviceConfig(
            device_type=DeviceType.RTLSDR,
            sample_rate=SAMPLE_RATE,
            center_freq=CENTER_FREQ,
            gain=30.0  # Автоматическая регулировка усиления
        )
        device = RTLSDRDevice(device_config)
        device.open()
        print(f"✅ Устройство подключено: {device.info}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        print("Убедитесь что RTL-SDR подключен!")
        import traceback
        traceback.print_exc()
        return
    
    # Процессор и анализатор
    config = DetectionConfig(fft_size=1024)
    processor = SignalProcessor(config)
    analyzer = InterferenceAnalyzer(wideband_threshold_hz=10e6)  # 10 МГц - порог "широкой" помехи
    
    print()
    print("=" * 80)
    print("ШАГ 1: Запись ЧИСТОГО спектра (без помех)")
    print("=" * 80)
    print()
    print("⚠️  УБЕДИТЕСЬ, ЧТО МИКСЕР ВЫКЛЮЧЕН!")
    print("Записываю эталонный спектр (5 секунд)...")
    print()
    
    # Записываем базовую линию (миксер выключен)
    baseline_samples = []
    for i in range(10):  # 10 измерений
        samples = device.read_samples(config.fft_size * 4)
        spectrum = processor.compute_spectrum(
            samples, 
            CENTER_FREQ, 
            SAMPLE_RATE,
            time.time()
        )
        baseline_samples.append(spectrum)
        print(f"  Замер {i+1}/10: средняя мощность {spectrum.avg_power:.1f} дБ")
        time.sleep(0.5)
    
    # Усредняем базовую линию
    import numpy as np
    avg_baseline_power = np.mean([s.power_db for s in baseline_samples], axis=0)
    baseline_spectrum = baseline_samples[0]  # Берём структуру первого
    baseline_spectrum.power_db = avg_baseline_power
    
    analyzer.set_baseline(baseline_spectrum)
    
    print()
    print("✅ Базовая линия записана!")
    print(f"   Средний уровень шума: {baseline_spectrum.avg_power:.1f} дБ")
    print()
    
    input("Нажмите ENTER когда будете готовы включить миксер...")
    
    print()
    print("=" * 80)
    print("ШАГ 2: Обнаружение помех")
    print("=" * 80)
    print()
    print("🔌 ВКЛЮЧИТЕ МИКСЕР СЕЙЧАС!")
    print()
    print("Жду 3 секунды...")
    time.sleep(3)
    
    print("Записываю спектр С ПОМЕХАМИ (5 секунд)...")
    print()
    
    # Записываем спектр с включённым миксером
    interference_samples = []
    for i in range(10):
        samples = device.read_samples(config.fft_size * 4)
        spectrum = processor.compute_spectrum(
            samples,
            CENTER_FREQ,
            SAMPLE_RATE,
            time.time()
        )
        interference_samples.append(spectrum)
        print(f"  Замер {i+1}/10: средняя мощность {spectrum.avg_power:.1f} дБ")
        time.sleep(0.5)
    
    # Усредняем
    avg_interference_power = np.mean([s.power_db for s in interference_samples], axis=0)
    test_spectrum = interference_samples[0]
    test_spectrum.power_db = avg_interference_power
    
    print()
    print("=" * 80)
    print("РЕЗУЛЬТАТЫ АНАЛИЗА")
    print("=" * 80)
    print()
    
    # Анализируем помехи
    interferences = analyzer.detect_interference(
        test_spectrum,
        threshold_db=-70,  # Низкий порог, чтобы видеть даже слабые помехи
        min_bandwidth_hz=100e3  # Минимум 100 кГц ширина
    )
    
    # Выводим отчёт
    report = analyzer.print_report(interferences)
    print(report)
    
    # Дополнительная статистика
    if interferences:
        print()
        print("📊 РЕКОМЕНДАЦИИ:")
        print()
        
        wideband = [i for i in interferences if i.is_wideband]
        if wideband:
            print(f"⚠️  Обнаружено {len(wideband)} широкополосных помех!")
            print("   Это типично для:")
            print("   - Коллекторных двигателей (миксер, дрель)")
            print("   - Сварочных аппаратов")
            print("   - Плохих контактов (искрение)")
            print()
            print("   Решение:")
            print("   - Установите ферритовый фильтр на кабель питания")
            print("   - Используйте сетевой фильтр с подавлением помех")
            print("   - Разнесите источник помехи и антенну на 5+ метров")
        
        print()
        print("🎯 Для системы обнаружения дронов:")
        print(f"   - Добавьте частоты {[f'{i.center_freq/1e6:.1f} МГц' for i in interferences[:3]]} в чёрный список")
        print("   - Или увеличьте порог детекции на этих частотах")
    
    # Закрываем устройство
    device.close()
    print()
    print("✅ Тест завершён!")

if __name__ == "__main__":
    main()
