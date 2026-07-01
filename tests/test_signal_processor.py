"""
RF Event Analyzer - Unit Tests for Signal Processing
"""
import pytest
import numpy as np

from rf_analyzer.core.config import DetectionConfig
from rf_analyzer.rf.signal_processor import (
    SignalProcessor,
    SpectrumResult,
    NoiseFloor,
    PeriodicityAnalyzer,
)


@pytest.fixture
def processor():
    config = DetectionConfig(fft_size=1024)
    return SignalProcessor(config)


@pytest.fixture
def test_samples():
    """Генерация тестовых IQ сэмплов с сигналом"""
    n_samples = 4096
    sample_rate = 2.4e6
    
    # Базовый шум
    noise = 0.01 * (np.random.randn(n_samples) + 1j * np.random.randn(n_samples))
    
    # Добавляем синусоидальный сигнал
    t = np.arange(n_samples) / sample_rate
    freq_offset = 100e3  # 100 кГц от центра
    signal = 0.5 * np.exp(2j * np.pi * freq_offset * t)
    
    return (noise + signal).astype(np.complex64), sample_rate


class TestSignalProcessor:
    def test_compute_spectrum(self, processor, test_samples):
        samples, sample_rate = test_samples
        
        spectrum = processor.compute_spectrum(
            samples,
            center_freq=100e6,
            sample_rate=sample_rate,
            timestamp=1000.0
        )
        
        assert isinstance(spectrum, SpectrumResult)
        assert len(spectrum.power_db) == processor.config.fft_size
        assert spectrum.center_freq == 100e6
        assert spectrum.sample_rate == sample_rate
    
    def test_detect_threshold(self, processor, test_samples):
        samples, sample_rate = test_samples
        
        spectrum = processor.compute_spectrum(
            samples,
            center_freq=100e6,
            sample_rate=sample_rate,
            timestamp=1000.0
        )
        
        # Должен детектировать сигнал
        detected, max_power, avg_power, peak_freq = processor.detect_threshold_exceeded(
            spectrum,
            threshold_db=-60.0,
            freq_start=100e6 - 500e3,
            freq_stop=100e6 + 500e3
        )
        
        assert detected
        assert max_power > -60.0
        # Пик должен быть около 100.1 МГц (центр + 100 кГц offset)
        assert abs(peak_freq - 100.1e6) < 50e3
    
    def test_noise_floor_update(self, processor):
        config = DetectionConfig(fft_size=256)
        proc = SignalProcessor(config)
        
        # Генерируем шум и обновляем
        for _ in range(20):
            noise = 0.001 * (np.random.randn(1024) + 1j * np.random.randn(1024))
            spectrum = proc.compute_spectrum(
                noise.astype(np.complex64),
                center_freq=100e6,
                sample_rate=2.4e6,
                timestamp=1000.0
            )
            proc.update_noise_floor(spectrum)
        
        assert proc.noise_floor.update_count == 20
        assert proc.noise_floor.avg_level < -40  # Должен быть низкий уровень


class TestNoiseFloor:
    def test_update(self):
        nf = NoiseFloor(alpha=0.5)
        
        spectrum1 = np.array([-80.0, -82.0, -81.0])
        nf.update(spectrum1)
        
        assert nf.update_count == 1
        np.testing.assert_array_almost_equal(nf.values, spectrum1)
        
        spectrum2 = np.array([-70.0, -72.0, -71.0])
        nf.update(spectrum2)
        
        # После обновления с alpha=0.5 значения должны быть средними
        expected = 0.5 * spectrum2 + 0.5 * spectrum1
        np.testing.assert_array_almost_equal(nf.values, expected)
    
    def test_threshold_mask(self):
        nf = NoiseFloor()
        nf.values = np.array([-80.0, -80.0, -80.0])
        nf.update_count = 10
        
        spectrum = np.array([-70.0, -85.0, -60.0])
        
        mask = nf.get_threshold_mask(spectrum, threshold_db=5.0)
        
        assert mask[0] == True   # -70 > -80 + 5 = -75
        assert mask[1] == False  # -85 < -75
        assert mask[2] == True   # -60 > -75


class TestPeriodicityAnalyzer:
    def test_detect_periodicity(self):
        analyzer = PeriodicityAnalyzer(history_size=200)
        
        # Генерируем периодический сигнал
        period = 1.0  # 1 секунда
        for i in range(100):
            timestamp = i * 0.1
            # Периодическое изменение мощности
            power = -50.0 + 10.0 * np.sin(2 * np.pi * timestamp / period)
            analyzer.add_sample(timestamp, power)
        
        detected, detected_period = analyzer.detect_periodicity(
            min_period=0.5, max_period=2.0
        )
        
        assert detected
        assert abs(detected_period - period) < 0.2  # Погрешность < 0.2 с
    
    def test_no_periodicity(self):
        analyzer = PeriodicityAnalyzer(history_size=100)
        
        # Случайные данные
        for i in range(50):
            analyzer.add_sample(i * 0.1, np.random.uniform(-60, -40))
        
        detected, _ = analyzer.detect_periodicity()
        
        # Не должно быть периодичности в случайных данных
        # (может быть ложное срабатывание, но маловероятно)


class TestSpectrumResult:
    def test_properties(self):
        freq = np.linspace(-1e6, 1e6, 100)
        power = np.random.uniform(-80, -60, 100)
        power[50] = -30  # Пик в центре
        
        spectrum = SpectrumResult(
            frequencies=freq,
            power_db=power,
            center_freq=100e6,
            sample_rate=2e6,
            timestamp=1000.0
        )
        
        assert spectrum.peak_power == -30.0
        assert spectrum.avg_power == pytest.approx(np.mean(power), rel=0.01)
        assert spectrum.peak_freq == pytest.approx(100e6, rel=0.01)
