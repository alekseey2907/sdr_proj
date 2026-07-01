"""
RF Event Analyzer - SigMF Export
Signal Metadata Format - стандартный формат для SDR записей
https://github.com/gnuradio/SigMF
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from rf_analyzer.core.config import RFEvent

logger = logging.getLogger(__name__)


@dataclass
class SigMFCapture:
    """Описание захвата сигнала"""
    sample_start: int = 0
    frequency: float = 0.0  # Hz
    datetime: str = ""
    
    def to_dict(self) -> dict:
        d = {"core:sample_start": self.sample_start}
        if self.frequency:
            d["core:frequency"] = self.frequency
        if self.datetime:
            d["core:datetime"] = self.datetime
        return d


@dataclass  
class SigMFAnnotation:
    """Аннотация события в записи"""
    sample_start: int = 0
    sample_count: int = 0
    freq_lower_edge: float = 0.0
    freq_upper_edge: float = 0.0
    label: str = ""
    comment: str = ""
    
    def to_dict(self) -> dict:
        d = {
            "core:sample_start": self.sample_start,
            "core:sample_count": self.sample_count,
        }
        if self.freq_lower_edge:
            d["core:freq_lower_edge"] = self.freq_lower_edge
        if self.freq_upper_edge:
            d["core:freq_upper_edge"] = self.freq_upper_edge
        if self.label:
            d["core:label"] = self.label
        if self.comment:
            d["core:comment"] = self.comment
        return d


@dataclass
class SigMFGlobal:
    """Глобальные метаданные SigMF"""
    datatype: str = "cf32_le"  # complex float32 little-endian
    sample_rate: float = 2.4e6
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    recorder: str = "RF Event Analyzer Pro"
    hw: str = ""
    
    # Расширения
    extensions: list = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "core:datatype": self.datatype,
            "core:sample_rate": self.sample_rate,
            "core:version": self.version,
            "core:description": self.description,
            "core:author": self.author,
            "core:recorder": self.recorder,
            "core:hw": self.hw,
            "core:extensions": self.extensions,
        }


class SigMFRecording:
    """Запись в формате SigMF"""
    
    def __init__(self, 
                 sample_rate: float = 2.4e6,
                 center_freq: float = 100e6,
                 description: str = "",
                 hw: str = "RTL-SDR"):
        
        self.global_meta = SigMFGlobal(
            sample_rate=sample_rate,
            description=description,
            hw=hw,
        )
        
        self.captures: list[SigMFCapture] = []
        self.annotations: list[SigMFAnnotation] = []
        self._samples: list[NDArray[np.complex64]] = []
        self._total_samples = 0
        
        # Добавляем начальный capture
        self.add_capture(center_freq)
    
    def add_capture(self, frequency: float, timestamp: datetime = None) -> None:
        """Добавить новый захват (смена частоты)"""
        capture = SigMFCapture(
            sample_start=self._total_samples,
            frequency=frequency,
            datetime=timestamp.isoformat() if timestamp else datetime.utcnow().isoformat() + "Z",
        )
        self.captures.append(capture)
    
    def add_samples(self, samples: NDArray[np.complex64]) -> None:
        """Добавить сэмплы"""
        self._samples.append(samples)
        self._total_samples += len(samples)
    
    def add_annotation(self, event: RFEvent, sample_rate: float = None) -> None:
        """Добавить аннотацию события"""
        if sample_rate is None:
            sample_rate = self.global_meta.sample_rate
        
        # Вычисляем позицию в сэмплах (приблизительно)
        sample_start = max(0, self._total_samples - int(event.duration_ms * sample_rate / 1000))
        sample_count = int(event.duration_ms * sample_rate / 1000)
        
        # Полоса частот
        bandwidth = event.bandwidth if hasattr(event, 'bandwidth') and event.bandwidth else sample_rate / 2
        
        annotation = SigMFAnnotation(
            sample_start=sample_start,
            sample_count=sample_count,
            freq_lower_edge=event.center_freq - bandwidth / 2,
            freq_upper_edge=event.center_freq + bandwidth / 2,
            label=event.event_type.value,
            comment=f"Range: {event.range_name}, Power: {event.max_power_db:.1f} dB",
        )
        self.annotations.append(annotation)
    
    def to_meta_dict(self) -> dict:
        """Получить метаданные как словарь"""
        return {
            "global": self.global_meta.to_dict(),
            "captures": [c.to_dict() for c in self.captures],
            "annotations": [a.to_dict() for a in self.annotations],
        }
    
    def save(self, base_path: Path) -> tuple[Path, Path]:
        """Сохранить запись
        
        Returns:
            Tuple of (meta_path, data_path)
        """
        base_path = Path(base_path)
        
        # Пути файлов
        meta_path = base_path.with_suffix(".sigmf-meta")
        data_path = base_path.with_suffix(".sigmf-data")
        
        # Сохраняем метаданные
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(self.to_meta_dict(), f, indent=2)
        
        # Сохраняем данные
        if self._samples:
            all_samples = np.concatenate(self._samples)
            all_samples.astype(np.complex64).tofile(data_path)
        else:
            # Создаём пустой файл
            data_path.touch()
        
        logger.info(f"SigMF recording saved: {meta_path}")
        return meta_path, data_path
    
    @classmethod
    def load(cls, base_path: Path) -> SigMFRecording:
        """Загрузить запись"""
        base_path = Path(base_path)
        
        # Определяем пути
        if base_path.suffix == ".sigmf-meta":
            meta_path = base_path
            data_path = base_path.with_suffix(".sigmf-data")
        elif base_path.suffix == ".sigmf-data":
            data_path = base_path
            meta_path = base_path.with_suffix(".sigmf-meta")
        else:
            meta_path = base_path.with_suffix(".sigmf-meta")
            data_path = base_path.with_suffix(".sigmf-data")
        
        # Загружаем метаданные
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        
        global_meta = meta.get("global", {})
        
        recording = cls(
            sample_rate=global_meta.get("core:sample_rate", 2.4e6),
            description=global_meta.get("core:description", ""),
            hw=global_meta.get("core:hw", ""),
        )
        
        # Загружаем captures
        recording.captures = []
        for c in meta.get("captures", []):
            recording.captures.append(SigMFCapture(
                sample_start=c.get("core:sample_start", 0),
                frequency=c.get("core:frequency", 0),
                datetime=c.get("core:datetime", ""),
            ))
        
        # Загружаем annotations
        recording.annotations = []
        for a in meta.get("annotations", []):
            recording.annotations.append(SigMFAnnotation(
                sample_start=a.get("core:sample_start", 0),
                sample_count=a.get("core:sample_count", 0),
                freq_lower_edge=a.get("core:freq_lower_edge", 0),
                freq_upper_edge=a.get("core:freq_upper_edge", 0),
                label=a.get("core:label", ""),
                comment=a.get("core:comment", ""),
            ))
        
        # Загружаем данные
        if data_path.exists():
            samples = np.fromfile(data_path, dtype=np.complex64)
            recording._samples = [samples]
            recording._total_samples = len(samples)
        
        return recording


def export_events_to_sigmf(events: list, 
                          samples: NDArray[np.complex64],
                          sample_rate: float,
                          center_freq: float,
                          output_path: Path,
                          hw: str = "RTL-SDR") -> Path:
    """Экспорт событий и сэмплов в SigMF формат"""
    
    recording = SigMFRecording(
        sample_rate=sample_rate,
        center_freq=center_freq,
        description=f"RF Events export - {len(events)} events",
        hw=hw,
    )
    
    recording.add_samples(samples)
    
    for event in events:
        recording.add_annotation(event, sample_rate)
    
    meta_path, data_path = recording.save(output_path)
    return meta_path
