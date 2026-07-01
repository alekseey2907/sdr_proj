"""
RF Event Analyzer - Interference (Помехи) Analyzer
Модуль для анализа и идентификации источников помех (миксеры, дрели, трансформаторы)
"""
import logging
from dataclasses import dataclass
from typing import List

import numpy as np

from rf_analyzer.rf.signal_processor import SpectrumResult

logger = logging.getLogger(__name__)


@dataclass
class InterferenceSource:
    """Источник помех"""
    name: str
    center_freq: float  # Центральная частота (Гц)
    bandwidth: float    # Ширина помехи (Гц)
    max_power_db: float # Максимальная мощность
    avg_power_db: float # Средняя мощность
    is_wideband: bool   # Широкополосная помеха (>10 МГц)
    
    @property
    def interference_type(self) -> str:
        """Тип помехи по характеристикам"""
        if self.bandwidth > 100e6:  # > 100 МГц
            return "Бытовая техника (миксер, дрель, сварка)"
        elif self.bandwidth > 10e6:  # > 10 МГц
            return "Импульсная помеха (плохой контакт, искра)"
        elif self.bandwidth > 1e6:   # > 1 МГц
            return "Широкополосный сигнал (дрон или Wi-Fi)"
        elif self.bandwidth < 50e3:  # < 50 кГц
            return "Узкополосный сигнал (рация, брелок)"
        else:
            return "Неизвестный источник"


class InterferenceAnalyzer:
    """Анализатор помех"""
    
    def __init__(self, wideband_threshold_hz: float = 10e6):
        """
        Args:
            wideband_threshold_hz: Порог ширины для определения "широкополосной" помехи (по умолчанию 10 МГц)
        """
        self.wideband_threshold = wideband_threshold_hz
        self._baseline_spectrum: SpectrumResult | None = None
        
    def set_baseline(self, spectrum: SpectrumResult) -> None:
        """Установить базовую линию (эталонный спектр без помех)"""
        self._baseline_spectrum = spectrum
        logger.info("Baseline spectrum set (reference for interference detection)")
    
    def detect_interference(
        self, 
        spectrum: SpectrumResult,
        threshold_db: float = -60,
        min_bandwidth_hz: float = 100e3  # Минимальная ширина для детекции (100 кГц)
    ) -> List[InterferenceSource]:
        """
        Обнаружить источники помех
        
        Args:
            spectrum: Текущий спектр
            threshold_db: Порог обнаружения (дБ)
            min_bandwidth_hz: Минимальная ширина для регистрации помехи
            
        Returns:
            Список обнаруженных источников помех
        """
        from scipy import signal as scipy_signal
        
        interferences = []
        
        # Если есть baseline - вычисляем разницу
        if self._baseline_spectrum is not None:
            # Превышение над базовой линией
            power_diff = spectrum.power_db - self._baseline_spectrum.power_db
        else:
            power_diff = spectrum.power_db
        
        # Находим пики (участки с превышением порога)
        peaks, properties = scipy_signal.find_peaks(
            power_diff, 
            height=threshold_db,
            prominence=5  # Минимальная "выпуклость" пика (5 дБ)
        )
        
        if len(peaks) == 0:
            return []
        
        # Измеряем ширину каждого пика
        widths_tuple = scipy_signal.peak_widths(power_diff, peaks, rel_height=0.5)
        widths_bins = widths_tuple[0]
        
        # Частотное разрешение
        freq_resolution = spectrum.sample_rate / len(spectrum.power_db)
        
        for i, peak_idx in enumerate(peaks):
            width_bins = widths_bins[i]
            width_hz = width_bins * freq_resolutionра
            
            # Фильтруем слишком узкие помехи
            if width_hz < min_bandwidth_hz:
                continue
            
            # Характеристики помехи
            center_freq = spectrum.freq_hz[peak_idx]
            max_power = spectrum.power_db[peak_idx]
            
            # Средняя мощность в пределах ширины пика
            left_idx = max(0, int(peak_idx - width_bins / 2))
            right_idx = min(len(spectrum.power_db) - 1, int(peak_idx + width_bins / 2))
            avg_power = float(np.mean(spectrum.power_db[left_idx:right_idx]))
            
            is_wideband = width_hz > self.wideband_threshold
            
            interference = InterferenceSource(
                name=f"Interference_{center_freq/1e6:.1f}MHz",
                center_freq=center_freq,
                bandwidth=width_hz,
                max_power_db=max_power,
                avg_power_db=avg_power,
                is_wideband=is_wideband
            )
            
            interferences.append(interference)
            
            logger.info(
                f"Interference detected: {center_freq/1e6:.2f} MHz, "
                f"width: {width_hz/1e6:.2f} MHz, "
                f"type: {interference.interference_type}"
            )
        
        return interferences
    
    def print_report(self, interferences: List[InterferenceSource]) -> str:
        """Сформировать текстовый отчёт о помехах"""
        if not interferences:
            return "✅ Помех не обнаружено (эфир чистый)"
        
        report_lines = [
            "=" * 80,
            f"🔴 ОБНАРУЖЕНО ПОМЕХ: {len(interferences)}",
            "=" * 80,
            ""
        ]
        
        for i, intf in enumerate(interferences, 1):
            report_lines.extend([
                f"Помеха #{i}:",
                f"  Частота:     {intf.center_freq/1e6:.2f} МГц",
                f"  Ширина:      {intf.bandwidth/1e6:.2f} МГц",
                f"  Мощность:    {intf.max_power_db:.1f} дБ (макс), {intf.avg_power_db:.1f} дБ (средн.)",
                f"  Тип:         {intf.interference_type}",
                ""
            ])
        
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
