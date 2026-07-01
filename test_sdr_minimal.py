#!/usr/bin/env python
# Минимальный тест SDR

print("Импортируем библиотеку...")
from rtlsdr import RtlSdr

print("Ищем устройства...")
devices = RtlSdr.get_device_serial_addresses()
print(f"Найдено устройств: {len(devices)}")
print(f"Серийники: {devices}")

if len(devices) > 0:
    print("\nПопытка подключения...")
    sdr = RtlSdr(device_index=0)
    print(f"✅ Подключено!")
    print(f"Sample rate: {sdr.sample_rate}")
    print(f"Center freq: {sdr.center_freq}")
    print(f"Gain: {sdr.gain}")
    sdr.close()
    print("Закрыто успешно")
