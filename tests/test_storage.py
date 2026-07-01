"""
RF Event Analyzer - Unit Tests for Event Storage
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile

from rf_analyzer.core.config import EventType, RFEvent
from rf_analyzer.storage.event_storage import EventStorage


@pytest.fixture
def storage():
    """Создание временной БД для тестов"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    
    storage = EventStorage(db_path)
    yield storage
    
    storage.close()
    db_path.unlink()


@pytest.fixture
def sample_event():
    return RFEvent(
        start_time=datetime.now(),
        end_time=datetime.now() + timedelta(seconds=1),
        duration_ms=1000.0,
        range_name="Test Range",
        center_freq=433.5e6,
        bandwidth=1e6,
        max_power_db=-50.0,
        avg_power_db=-55.0,
        event_type=EventType.THRESHOLD_EXCEEDED,
        comment="Test event",
    )


class TestEventStorage:
    def test_save_and_get_event(self, storage, sample_event):
        event_id = storage.save_event(sample_event)
        
        assert event_id > 0
        
        loaded = storage.get_event(event_id)
        
        assert loaded is not None
        assert loaded.id == event_id
        assert loaded.range_name == sample_event.range_name
        assert loaded.max_power_db == sample_event.max_power_db
    
    def test_get_events_filtered(self, storage):
        # Создаём несколько событий
        for i in range(5):
            event = RFEvent(
                start_time=datetime.now() - timedelta(hours=i),
                duration_ms=100.0,
                range_name=f"Range {i % 2}",
                center_freq=100e6,
                bandwidth=1e6,
                max_power_db=-50.0 - i,
                avg_power_db=-55.0,
                event_type=EventType.IMPULSE if i % 2 else EventType.THRESHOLD_EXCEEDED,
            )
            storage.save_event(event)
        
        # Фильтр по диапазону
        events = storage.get_events(range_name="Range 0")
        assert len(events) == 3
        
        # Фильтр по типу
        events = storage.get_events(event_type=EventType.IMPULSE)
        assert len(events) == 2
    
    def test_get_statistics(self, storage):
        for i in range(10):
            event = RFEvent(
                start_time=datetime.now(),
                duration_ms=100.0 + i * 10,
                range_name="Test",
                center_freq=100e6,
                bandwidth=1e6,
                max_power_db=-50.0 + i,
                avg_power_db=-55.0,
                event_type=EventType.THRESHOLD_EXCEEDED,
            )
            storage.save_event(event)
        
        stats = storage.get_statistics()
        
        assert stats["total_events"] == 10
        assert stats["max_power_db"] == -41.0
        assert "Test" in stats["by_range"]
    
    def test_count_events(self, storage, sample_event):
        for _ in range(5):
            storage.save_event(sample_event)
        
        count = storage.count_events()
        assert count == 5
    
    def test_metadata(self, storage):
        storage.set_metadata("test_key", {"value": 123})
        
        result = storage.get_metadata("test_key")
        assert result == {"value": 123}
        
        # Несуществующий ключ
        result = storage.get_metadata("nonexistent", default="default")
        assert result == "default"
