"""
RF Event Analyzer - Signal Processing Module
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray
from scipy import signal as scipy_signal

if TYPE_CHECKING:
    from rf_analyzer.core.config import DetectionConfig

logger = logging.getLogger(__name__)


@dataclass
class SpectrumResult:
    """Результат FFT анализа"""
    frequencies: NDArray[np.float64]  # Частоты относительно центральной
    power_db: NDArray[np.float64]     # Мощность в дБ
    center_freq: float                 # Центральная частота
    sample_rate: float                 # Частота дискретизации
    timestamp: float                   # Временная метка
    
    @property
    def freq_hz(self) -> NDArray[np.float64]:
        """Абсолютные частоты в Гц"""
        return self.frequencies + self.center_freq
    
    @property
    def peak_power(self) -> float:
        return float(np.max(self.power_db))
    
    @property
    def avg_power(self) -> float:
        return float(np.mean(self.power_db))
    
    @property
    def peak_freq(self) -> float:
        idx = np.argmax(self.power_db)
        return float(self.freq_hz[idx])


@dataclass
class NoiseFloor:
    """Модель уровня шума"""
    values: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    update_count: int = 0
    alpha: float = 0.1  # Коэффициент экспоненциального сглаживания
    
    def update(self, spectrum: NDArray[np.float64]) -> None:
        """Обновление оценки уровня шума"""
        if len(self.values) == 0 or len(self.values) != len(spectrum):
            self.values = spectrum.copy()
        else:
            # Экспоненциальное сглаживание
            self.values = self.alpha * spectrum + (1 - self.alpha) * self.values
        self.update_count += 1
    
    @property
    def avg_level(self) -> float:
        if len(self.values) == 0:
            return -100.0
        return float(np.mean(self.values))
    
    def get_threshold_mask(self, spectrum: NDArray[np.float64], 
                          threshold_db: float) -> NDArray[np.bool_]:
        """Получить маску превышения порога над уровнем шума"""
        if len(self.values) == 0 or len(self.values) != len(spectrum):
            return np.zeros(len(spectrum), dtype=bool)
        return spectrum > (self.values + threshold_db)


class SignalProcessor:
    """Процессор сигналов для FFT анализа"""
    
    def __init__(self, config: DetectionConfig):
        self.config = config
        self._window = scipy_signal.windows.blackmanharris(config.fft_size)
        self._noise_floor = NoiseFloor()
        self.last_spectrum: SpectrumResult | None = None  # Последний вычисленный спектр
    
    def compute_spectrum(
        self, 
        samples: NDArray[np.complex64],
        center_freq: float,
        sample_rate: float,
        timestamp: float
    ) -> SpectrumResult:
        """Вычисление спектра мощности из IQ сэмплов"""
        fft_size = self.config.fft_size
        
        # Если сэмплов меньше чем FFT размер - дополняем нулями
        if len(samples) < fft_size:
            samples = np.pad(samples, (0, fft_size - len(samples)))
        
        # DC offset removal - убираем постоянную составляющую (артефакт RTL-SDR)
        samples = samples - np.mean(samples)
        
        # Усреднение по нескольким FFT для улучшения SNR
        num_ffts = len(samples) // fft_size
        if num_ffts == 0:
            num_ffts = 1
        
        psd_sum = np.zeros(fft_size)
        
        for i in range(num_ffts):
            start = i * fft_size
            segment = samples[start:start + fft_size]
            
            if len(segment) < fft_size:
                segment = np.pad(segment, (0, fft_size - len(segment)))
            
            # Применяем окно
            windowed = segment * self._window
            
            # FFT
            fft_result = np.fft.fftshift(np.fft.fft(windowed))
            
            # Спектр мощности
            psd = np.abs(fft_result) ** 2
            psd_sum += psd
        
        # Усреднение
        psd_avg = psd_sum / num_ffts
        
        # Зануляем центральные бины (DC spike артефакт RTL-SDR)
        # Обычно DC spike занимает 1-3 бина в центре
        center = fft_size // 2
        dc_notch_width = 3  # Количество бинов для зануления
        for offset in range(-dc_notch_width // 2, dc_notch_width // 2 + 1):
            if 0 <= center + offset < fft_size:
                # Интерполируем значение из соседних бинов
                left_idx = center - dc_notch_width
                right_idx = center + dc_notch_width
                if left_idx >= 0 and right_idx < fft_size:
                    psd_avg[center + offset] = (psd_avg[left_idx] + psd_avg[right_idx]) / 2
        
        # Нормализация и перевод в дБ
        # Учитываем энергию окна
        window_energy = np.sum(self._window ** 2)
        psd_normalized = psd_avg / window_energy
        
        # Перевод в дБ с защитой от log(0)
        power_db = 10 * np.log10(psd_normalized + 1e-20)
        
        # Частотная ось
        frequencies = np.fft.fftshift(np.fft.fftfreq(fft_size, 1/sample_rate))
        
        result = SpectrumResult(
            frequencies=frequencies,
            power_db=power_db,
            center_freq=center_freq,
            sample_rate=sample_rate,
            timestamp=timestamp
        )
        
        # Сохраняем последний спектр
        self.last_spectrum = result
        
        return result
    
    def update_noise_floor(self, spectrum: SpectrumResult) -> None:
        """Обновить оценку уровня шума"""
        self._noise_floor.update(spectrum.power_db)
    
    @property
    def noise_floor(self) -> NoiseFloor:
        return self._noise_floor
    
    def detect_threshold_exceeded(
        self, 
        spectrum: SpectrumResult,
        threshold_db: float,
        freq_start: float,
        freq_stop: float
    ) -> tuple[bool, float, float, float]:
        """
        Детекция превышения порога в заданном диапазоне
        
        Returns:
            (detected, max_power, avg_power, peak_freq)
        """
        # Находим индексы для заданного диапазона
        freq_hz = spectrum.freq_hz
        mask = (freq_hz >= freq_start) & (freq_hz <= freq_stop)
        
        if not np.any(mask):
            return False, -100.0, -100.0, 0.0
        
        power_in_range = spectrum.power_db[mask]
        freq_in_range = freq_hz[mask]
        
        max_power = float(np.max(power_in_range))
        avg_power = float(np.mean(power_in_range))
        peak_idx = np.argmax(power_in_range)
        peak_freq = float(freq_in_range[peak_idx])
        
        detected = max_power > threshold_db
        
        return detected, max_power, avg_power, peak_freq
    
    def detect_impulse(
        self,
        spectrum: SpectrumResult,
        impulse_threshold_db: float,
        freq_start: float,
        freq_stop: float
    ) -> tuple[bool, float]:
        """
        Детекция импульсной помехи (резкое превышение над шумом)
        
        Returns:
            (detected, excess_db)
        """
        if self._noise_floor.update_count < 10:
            return False, 0.0
        
        freq_hz = spectrum.freq_hz
        mask = (freq_hz >= freq_start) & (freq_hz <= freq_stop)
        
        if not np.any(mask):
            return False, 0.0
        
        power_in_range = spectrum.power_db[mask]
        noise_in_range = self._noise_floor.values[mask]
        
        # Превышение над шумом
        excess = power_in_range - noise_in_range
        max_excess = float(np.max(excess))
        
        detected = max_excess > impulse_threshold_db
        
        return detected, max_excess
    
    def detect_noise_floor_shift(
        self,
        spectrum: SpectrumResult,
        shift_threshold_db: float = 5.0
    ) -> tuple[bool, float]:
        """
        Детекция изменения уровня шума
        
        Returns:
            (detected, shift_db)
        """
        if self._noise_floor.update_count < 20:
            return False, 0.0
        
        current_avg = spectrum.avg_power
        baseline_avg = self._noise_floor.avg_level
        
        shift = current_avg - baseline_avg
        detected = abs(shift) > shift_threshold_db
        
        return detected, shift
    
    def get_band_power(
        self,
        spectrum: SpectrumResult,
        freq_start: float,
        freq_stop: float
    ) -> tuple[float, float]:
        """
        Получить мощность в заданной полосе
        
        Returns:
            (max_power, avg_power)
        """
        freq_hz = spectrum.freq_hz
        mask = (freq_hz >= freq_start) & (freq_hz <= freq_stop)
        
        if not np.any(mask):
            return -100.0, -100.0
        
        power_in_range = spectrum.power_db[mask]
        return float(np.max(power_in_range)), float(np.mean(power_in_range))
    
    def detect_signal_width(
        self,
        spectrum: SpectrumResult,
        threshold_db: float,
        freq_start: float,
        freq_stop: float
    ) -> float:
        """
        Измерение ширины самого широкого сигнала в диапазоне.
        Используется для фильтрации узкополосных помех (брелки, рации).
        
        Returns:
            Ширина сигнала в Гц
        """
        freq_hz = spectrum.freq_hz
        mask = (freq_hz >= freq_start) & (freq_hz <= freq_stop)
        
        if not np.any(mask):
            return 0.0
        
        power_in_range = spectrum.power_db[mask]
        
        # Находим пики выше порога
        peaks, _ = scipy_signal.find_peaks(power_in_range, height=threshold_db)
        
        if len(peaks) == 0:
            return 0.0
        
        # Измеряем ширину пиков на уровне половины высоты
        widths_tuple = scipy_signal.peak_widths(power_in_range, peaks, rel_height=0.5)
        widths_indices = widths_tuple[0]
        
        if len(widths_indices) == 0:
            return 0.0
        
        # Берем самый широкий сигнал
        max_width_bins = np.max(widths_indices)
        
        # Переводим бины в Герцы
        freq_resolution = spectrum.sample_rate / self.config.fft_size
        width_hz = max_width_bins * freq_resolution
        
        return float(width_hz)
    
    def detect_signal_width(
        self,
        spectrum: SpectrumResult,
        threshold_db: float,
        freq_start: float,
        freq_stop: float
    ) -> float:
        """
        Измерение ширины самого широкого сигнала в диапазоне (для фильтрации узкополосных помех).
        Возвращает ширину в Гц.
        """
        freq_hz = spectrum.freq_hz
        mask = (freq_hz >= freq_start) & (freq_hz <= freq_stop)
        
        if not np.any(mask):
            return 0.0
        
        power_in_range = spectrum.power_db[mask]
        
        # 1. Находим пики, которые выше порога
        peaks, _ = scipy_signal.find_peaks(power_in_range, height=threshold_db)
        
        if len(peaks) == 0:
            return 0.0
            
        # 2. Измеряем ширину пиков на уровне половины высоты (примерно -3dB..-6dB от пика)
        # rel_height=0.5 означает измерение ширины на половине "проминенции" (выпуклости) пика
        widths_tuple = scipy_signal.peak_widths(power_in_range, peaks, rel_height=0.5)
        widths_indices = widths_tuple[0] # массив ширин в "бинах" (индексах)
        
        if len(widths_indices) == 0:
            return 0.0
        
        # 3. Берем самый широкий сигнал
        max_width_bins = np.max(widths_indices)
        
        # 4. Переводим бины в Герцы
        # Разрешение по частоте = частота дискретизации / размер FFT
        freq_resolution = spectrum.sample_rate / self.config.fft_size
        width_hz = max_width_bins * freq_resolution
        
        return float(width_hz)


class PeriodicityAnalyzer:
    """Анализатор периодической активности"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self._power_history: list[tuple[float, float]] = []  # (timestamp, power)
    
    def add_sample(self, timestamp: float, power: float) -> None:
        self._power_history.append((timestamp, power))
        if len(self._power_history) > self.history_size:
            self._power_history.pop(0)
    
    def detect_periodicity(self, min_period: float = 0.1, max_period: float = 60.0) -> tuple[bool, float]:
        """
        Детекция периодической активности
        
        Returns:
            (detected, period_seconds)
        """
        if len(self._power_history) < 20:
            return False, 0.0
        
        timestamps = np.array([t for t, _ in self._power_history])
        powers = np.array([p for _, p in self._power_history])
        
        # Нормализуем
        powers_norm = (powers - np.mean(powers)) / (np.std(powers) + 1e-10)
        
        # Автокорреляция
        autocorr = np.correlate(powers_norm, powers_norm, mode='full')
        autocorr = autocorr[len(autocorr)//2:]
        autocorr = autocorr / autocorr[0]
        
        # Временной шаг
        if len(timestamps) > 1:
            dt = np.mean(np.diff(timestamps))
        else:
            return False, 0.0
        
        # Ищем пики автокорреляции
        min_lag = int(min_period / dt)
        max_lag = min(int(max_period / dt), len(autocorr) - 1)
        
        if min_lag >= max_lag:
            return False, 0.0
        
        search_region = autocorr[min_lag:max_lag]
        if len(search_region) == 0:
            return False, 0.0
        
        # Находим максимум
        peak_idx = np.argmax(search_region) + min_lag
        peak_value = autocorr[peak_idx]
        
        # Порог для детекции периодичности
        if peak_value > 0.5:
            period = peak_idx * dt
            return True, period
        
        return False, 0.0
    
    def clear(self) -> None:
        self._power_history.clear()
