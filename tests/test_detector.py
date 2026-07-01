"""
RF Event Analyzer - Unit Tests for Event Detector
"""
import pytest
import numpy as np
from datetime import datetime

from rf_analyzer.core.config import DetectionConfig, EventType, FrequencyRange
from rf_analyzer.detection.detector import EventDetector
from rf_analyzer.rf.signal_processor import SpectrumResult


@pytest.fixture
def detector():
    config = DetectionConfig(
        fft_size=256,
        noise_floor_averaging=10,
        impulse_threshold_db=15.0,
        min_event_gap_ms=100.0,
    )
    
    ranges = [
        FrequencyRange(
            name="Test Range",
            start_freq=99.5e6,
            stop_freq=100.5e6,
            threshold_db=-60.0,
            min_duration_ms=50.0,
        )
    ]
    
    events = []
    detector = EventDetector(
        config=config,
        ranges=ranges,
        on_event_callback=lambda e: events.append(e)
    )
    detector._collected_events = events
    
    return detector


def create_spectrum(power_db: float, center_freq: float = 100e6, 
                   timestamp: float = 1000.0) -> SpectrumResult:
    """Создание тестового спектра"""
    fft_size = 256
    freq = np.linspace(-1e6, 1e6, fft_size)
    power = np.full(fft_size, power_db)
    
    return SpectrumResult(
        frequencies=freq,
        power_db=power,
        center_freq=center_freq,
        sample_rate=2e6,
        timestamp=timestamp
    )


class TestEventDetector:
    def test_no_event_below_threshold(self, detector):
        # Спектр ниже порога
        spectrum = create_spectrum(power_db=-70.0, timestamp=1.0)
        
        events = detector.process_spectrum(spectrum)
        
        assert len(events) == 0
    
    def test_event_above_threshold(self, detector):
        # Сначала прогреваем шумовой фон
        for i in range(15):
            spectrum = create_spectrum(power_db=-80.0, timestamp=float(i) * 0.1)
            detector.process_spectrum(spectrum)
        
        # Теперь подаём сигнал выше порога
        for i in range(5):
            spectrum = create_spectrum(power_db=-50.0, timestamp=2.0 + i * 0.1)
            detector.process_spectrum(spectrum)
        
        # Спускаем обратно
        spectrum = create_spectrum(power_db=-80.0, timestamp=3.0)
        events = detector.process_spectrum(spectrum)
        
        # Должно быть событие
        assert len(events) == 1
        assert events[0].range_name == "Test Range"
        assert events[0].max_power_db == -50.0
    
    def test_event_too_short(self, detector):
        # Прогрев
        for i in range(15):
            spectrum = create_spectrum(power_db=-80.0, timestamp=float(i) * 0.1)
            detector.process_spectrum(spectrum)
        
        # Очень короткий сигнал (1 спектр = несколько мс)
        spectrum = create_spectrum(power_db=-50.0, timestamp=2.0)
        detector.process_spectrum(spectrum)
        
        # Сразу спад
        spectrum = create_spectrum(power_db=-80.0, timestamp=2.01)
        events = detector.process_spectrum(spectrum)
        
        # Событие должно быть отфильтровано как слишком короткое
        assert len(events) == 0
    
    def test_flush_active_events(self, detector):
        # Прогрев
        for i in range(15):
            spectrum = create_spectrum(power_db=-80.0, timestamp=float(i) * 0.1)
            detector.process_spectrum(spectrum)
        
        # Активное событие
        for i in range(10):
            spectrum = create_spectrum(power_db=-50.0, timestamp=2.0 + i * 0.1)
            detector.process_spectrum(spectrum)
        
        # Flush без спада
        events = detector.flush()
        
        assert len(events) == 1
    
    def test_update_ranges(self, detector):
        new_ranges = [
            FrequencyRange(
                name="New Range",
                start_freq=200e6,
                stop_freq=201e6,
                threshold_db=-55.0,
            )
        ]
        
        detector.update_ranges(new_ranges)
        
        assert "New Range" in detector.ranges
        assert "Test Range" not in detector.ranges
    
    def test_stats(self, detector):
        stats = detector.get_stats()
        
        assert "spectrum_count" in stats
        assert "active_events" in stats
        assert "noise_floor_db" in stats
        assert stats["monitored_ranges"] == 1
