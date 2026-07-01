"""
RF Event Analyzer - Unit Tests for Core Config
"""
import pytest
from datetime import datetime
from pathlib import Path
import tempfile

from rf_analyzer.core.config import (
    AppConfig,
    DeviceConfig,
    DeviceType,
    DetectionConfig,
    EventType,
    FrequencyRange,
    OutputConfig,
    RFEvent,
)


class TestFrequencyRange:
    def test_center_freq(self):
        fr = FrequencyRange(
            name="Test",
            start_freq=100e6,
            stop_freq=110e6,
        )
        assert fr.center_freq == 105e6
    
    def test_bandwidth(self):
        fr = FrequencyRange(
            name="Test",
            start_freq=100e6,
            stop_freq=110e6,
        )
        assert fr.bandwidth == 10e6
    
    def test_to_dict_from_dict(self):
        fr = FrequencyRange(
            name="Test Range",
            start_freq=433e6,
            stop_freq=434e6,
            threshold_db=-65.0,
            min_duration_ms=50.0,
            enabled=True,
        )
        
        data = fr.to_dict()
        fr2 = FrequencyRange.from_dict(data)
        
        assert fr2.name == fr.name
        assert fr2.start_freq == fr.start_freq
        assert fr2.stop_freq == fr.stop_freq
        assert fr2.threshold_db == fr.threshold_db


class TestRFEvent:
    def test_generate_comment(self):
        event = RFEvent(
            start_time=datetime.now(),
            range_name="Test",
            center_freq=433.5e6,
            bandwidth=1e6,
            max_power_db=-50.0,
            avg_power_db=-55.0,
            duration_ms=150.0,
            event_type=EventType.IMPULSE,
        )
        
        comment = event.generate_comment()
        
        assert "433.500" in comment
        assert "Импульс" in comment
        assert "-50.0" in comment
    
    def test_to_dict_from_dict(self):
        event = RFEvent(
            id=1,
            start_time=datetime(2024, 1, 15, 10, 30, 0),
            end_time=datetime(2024, 1, 15, 10, 30, 1),
            duration_ms=1000.0,
            range_name="Test",
            center_freq=100e6,
            bandwidth=1e6,
            max_power_db=-50.0,
            avg_power_db=-55.0,
            event_type=EventType.THRESHOLD_EXCEEDED,
            comment="Test comment",
        )
        
        data = event.to_dict()
        event2 = RFEvent.from_dict(data)
        
        assert event2.id == event.id
        assert event2.start_time == event.start_time
        assert event2.event_type == event.event_type


class TestAppConfig:
    def test_save_load(self):
        config = AppConfig.default()
        config.ranges.append(
            FrequencyRange(
                name="Custom Range",
                start_freq=145e6,
                stop_freq=146e6,
            )
        )
        
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = Path(f.name)
        
        try:
            config.save(path)
            loaded = AppConfig.load(path)
            
            assert len(loaded.ranges) == len(config.ranges)
            assert loaded.device.sample_rate == config.device.sample_rate
        finally:
            path.unlink()
    
    def test_default(self):
        config = AppConfig.default()
        
        assert config.device.device_type == DeviceType.RTLSDR
        assert len(config.ranges) > 0
        assert config.detection.fft_size == 1024
