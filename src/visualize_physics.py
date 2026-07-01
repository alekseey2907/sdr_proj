import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate

# Конфигурация симуляции
fs = 1000  # Частота дискретизации (условная, для скорости)
duration = 2.0  # секунды
t = np.linspace(0, duration, int(fs * duration))

# ----------------------------------------------------
# 1. Симуляция ДРОНА (Высоко, Стабильно)
# ----------------------------------------------------
# Дрон летит на эшелоне. Обороты стабильны.
# Линия визирования (Line of Sight) -> Сигнал растет по 1/R^2, мало замираний.
drone_freq = 100 # 100 Гц = 6000 об/мин (типично для 2-тактного ДВС)
drone_rpm_jitter = 0.0005 # Очень низкий джиттер (круиз-контроль)
drone_signal = np.zeros_like(t)

current_time = 0
while current_time < duration:
    idx = int(current_time * fs)
    if idx < len(drone_signal):
        # Амплитуда плавно растет (дрон приближается)
        # Симулируем приближение на 10% за 2 секунды
        amp = 1.0 + (current_time * 0.2) 
        drone_signal[idx] = amp
    # Следующая искра (стабильный интервал)
    current_time += (1.0 / drone_freq) + np.random.normal(0, drone_rpm_jitter * (1.0/drone_freq))

# Добавляем немного шума эфира
drone_noisy = drone_signal + np.random.normal(0, 0.1, size=len(t))


# ----------------------------------------------------
# 2. Симуляция МОПЕДА (Низко, Хаос)
# ----------------------------------------------------
# Мопед едет по земле. Обороты скачут (газ/тормоз).
# Многолучевое распространение (дома, заборы) -> Сильные замирания амплитуды.
moped_freq = 60 # 60 Гц = 3600 об/мин
moped_rpm_jitter = 0.15 # 15% джиттер (ручка газа дрожит)
moped_signal = np.zeros_like(t)

# Профиль замираний (Multipath Fading)
# Случайное блуждание амплитуды
np.random.seed(42)
fading_profile = np.abs(np.cumsum(np.random.normal(0, 0.5, size=len(t))))
# Нормируем профиль, чтобы он скакал от 0.5 до 2.0
fading_profile = (fading_profile - np.min(fading_profile))
fading_profile = 0.5 + 1.5 * (fading_profile / np.max(fading_profile))

current_time = 0
while current_time < duration:
    idx = int(current_time * fs)
    if idx < len(moped_signal):
        # Амплитуда промодулирована замираниями
        amp = fading_profile[idx]
        moped_signal[idx] = amp
    # Следующая искра (сильный разброс интервалов)
    current_time += (1.0 / moped_freq) + np.random.normal(0, moped_rpm_jitter * (1.0/moped_freq))

moped_noisy = moped_signal + np.random.normal(0, 0.1, size=len(t))


# ----------------------------------------------------
# 3. Математика: АВТОКОРРЕЛЯЦИЯ (Суть алгоритма)
# ----------------------------------------------------
# Берем кусок 0.5 секунды
slice_len = int(0.5 * fs)
drone_slice = drone_noisy[:slice_len]
moped_slice = moped_noisy[:slice_len]

# Нормализация
drone_slice = (drone_slice - np.mean(drone_slice)) / (np.std(drone_slice) * len(drone_slice))
moped_slice = (moped_slice - np.mean(moped_slice)) / (np.std(moped_slice) * len(moped_slice))

lags = np.arange(-slice_len + 1, slice_len)
corr_drone = correlate(drone_slice, drone_slice, mode='full')
corr_moped = correlate(moped_slice, moped_slice, mode='full')

# Оставляем только положительную часть
half_len = len(corr_drone) // 2
lags = lags[half_len:]
corr_drone = corr_drone[half_len:]
corr_moped = corr_moped[half_len:]


# ----------------------------------------------------
# ОТРИСОВКА
# ----------------------------------------------------
fig = plt.figure(figsize=(14, 10))
plt.subplots_adjust(hspace=0.4)

# График 1: Временная область
ax1 = plt.subplot(2, 1, 1)
ax1.set_title("1. Что приходит на антенну (Сырой сигнал)", fontsize=14, fontweight='bold')
# Рисуем только первые 0.5 сек для наглядности
t_view = t[:500]
ax1.plot(t_view, drone_noisy[:500] + 2.5, label='ДРОН (Высоко): Идеальный ритм, чистая амплитуда', color='blue')
ax1.plot(t_view, moped_noisy[:500], label='МОПЕД (Земля): Скачет ритм, скачет амплитуда', color='red', alpha=0.7)
ax1.set_xlabel("Время (сек)")
ax1.set_yticks([])
ax1.legend(loc='upper right', fontsize=12)
ax1.grid(True, alpha=0.3)
ax1.text(0, 4.0, "ВРАГ: Математически идеальный сигнал", color='blue', fontweight='bold')
ax1.text(0, 1.5, "ШУМ: Хаотичный, рваный сигнал", color='red', fontweight='bold')

# График 2: Автокорреляция
ax2 = plt.subplot(2, 1, 2)
ax2.set_title("2. Как это видит твой Алгоритм (Автокорреляция)", fontsize=14, fontweight='bold')
ax2.plot(lags[:150], corr_drone[:150], label='ДРОН', color='blue', linewidth=2)
ax2.plot(lags[:150], corr_moped[:150], label='МОПЕД', color='red', linestyle='--', alpha=0.7)
ax2.set_xlabel("Сдвиг (Лаг)", fontsize=12)
ax2.set_ylabel("Сила совпадения", fontsize=12)
ax2.legend(fontsize=12)
ax2.grid(True, alpha=0.5)

# Аннотации на графике
ax2.annotate('ЧЕТКИЕ ПИКИ = ДРОН\nАлгоритм сразу видит "Сердцебиение"', 
             xy=(20, corr_drone[20]), xytext=(40, 0.8),
             arrowprops=dict(facecolor='black', shrink=0.05))

ax2.annotate('МЫЛО = МОПЕД\nАлгоритм игнорирует', 
             xy=(16, corr_moped[16]), xytext=(40, 0.2),
             arrowprops=dict(facecolor='red', shrink=0.05))

# Сохранение
output_file = 'physics_demo.png'
plt.savefig(output_file, dpi=100)
print(f"График сохранен в файл: {output_file}")
