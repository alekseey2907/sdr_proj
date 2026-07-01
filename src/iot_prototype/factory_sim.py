import time
import random
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict

@dataclass
class MotorReport:
    motor_id: int
    room_id: str
    status: str       # "OK", "WARNING", "CRITICAL"
    vibration_mm_s: float
    temperature_c: float
    battery_v: float
    timestamp: str

class VirtualMotor:
    def __init__(self, motor_id: int, room: str):
        self.motor_id = motor_id
        self.room = room
        # Состояние "здоровья" двигателя (0.0 - новый, 1.0 - труп)
        self.wear_level = random.uniform(0.0, 0.3) 
        self.is_running = True
        
    def simulate_tick(self) -> MotorReport:
        """Симуляция одного цикла измерения (раз в минуту)"""
        
        # 1. Симуляция физики
        base_vibration = 0.5 + (self.wear_level * 5.0) # Чем больше износ, тем выше вибрация
        
        # Добавляем шум измерения
        current_vibration = base_vibration + random.uniform(-0.1, 0.1)
        
        # Случайные скачки (ударная нагрузка)
        if random.random() < 0.05:
            current_vibration += random.uniform(1.0, 3.0)
            
        # Симуляция температуры
        current_temp = 45.0 + (self.wear_level * 20.0) + random.uniform(-2, 2)

        # 2. "Edge Computing" логика (то, что делает ESP32)
        status = "OK"
        if current_vibration > 2.5:
            status = "WARNING"
        if current_vibration > 7.0:
            status = "CRITICAL" # Авария!
            
        # Увеличиваем износ со временем (очень медленно)
        if self.is_running:
            self.wear_level += 0.0001
            
        # Иногда ломаем двигатель специально (для демо)
        if random.random() < 0.001 and self.motor_id == 13: # "Несчастливый" мотор
             self.wear_level = 0.9

        return MotorReport(
            motor_id=self.motor_id,
            room_id=self.room,
            status=status,
            vibration_mm_s=round(current_vibration, 2),
            temperature_c=round(current_temp, 1),
            battery_v=3.6,
            timestamp=datetime.now().isoformat()
        )

class VirtualFactory:
    def __init__(self, num_motors=50):
        self.motors = []
        for i in range(1, num_motors + 1):
            room = f"Цех №{random.randint(1, 4)}"
            self.motors.append(VirtualMotor(i, room))
            
    def run(self):
        print(f"\n--- ЗАПУСК ВИРТУАЛЬНОГО ЗАВОДА ({len(self.motors)} датчиков) ---")
        print("Сервер слушает порт 8080 (симуляция)...")
        print("Нажмите Ctrl+C для остановки\n")
        
        while True:
            t0 = time.time()
            reports = []
            alerts = []
            
            # Опрос всех датчиков
            for motor in self.motors:
                report = motor.simulate_tick()
                reports.append(report)
                if report.status != "OK":
                    alerts.append(report)
            
            # --- ВИЗУАЛИЗАЦИЯ (Замена Дашборда) ---
            self._print_dashboard(len(reports), alerts)
            
            # Ждем следующего цикла
            time.sleep(2.0) # Ускоренное время (1 секунда = 1 минута жизни)

    def _print_dashboard(self, total, alerts):
        # Очистка экрана (эмуляция)
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print(f"=== МОНИТОРИНГ ЗАВОДА | {datetime.now().strftime('%H:%M:%S')} ===")
        print(f"Всего датчиков в сети: {total}")
        
        print("\n[ СТАТУС СИСТЕМЫ ]")
        if not alerts:
             print("✅ НОРМА. Все узлы работают штатно.")
        else:
             print(f"❌ ВНИМАНИЕ! Обнаружено проблем: {len(alerts)}")
        
        print("\n" + "="*60)
        print(f"{'ID':<5} | {'ЦЕХ':<10} | {'СТАТУС':<10} | {'ВИБРАЦИЯ':<10} | {'ТЕМП.'}")
        print("-" * 60)
        
        # Сначала показываем критические, потом предупреждения
        sorted_alerts = sorted(alerts, key=lambda x: x.vibration_mm_s, reverse=True)
        
        for r in sorted_alerts:
            color_code = ""
            status_ico = "❓"
            if r.status == "WARNING":
                status_ico = "🟡 WRN"
            elif r.status == "CRITICAL":
                status_ico = "🔴 ALARM"
                
            print(f"#{r.motor_id:<4} | {r.room_id:<10} | {status_ico:<10} | {r.vibration_mm_s:>5} mm/s | {r.temperature_c}°C")
            
        if not alerts:
            print("(Список пуст. Инженер пьет кофе.)")
            
        print("="*60)
        print("\n(Симуляция: Данные обновляются каждые 2 секунды...)")

if __name__ == "__main__":
    factory = VirtualFactory(num_motors=100) # Симулируем 100 моторов
    factory.run()
