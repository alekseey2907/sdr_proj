"""
RF Event Analyzer - Core Configuration Models
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class DeviceType(Enum):
    RTLSDR = "rtlsdr"
    HACKRF = "hackrf"
    LIBRESDR = "libresdr"
    USRP = "usrp"
    SIMULATED = "simulated"


class EventType(Enum):
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    IMPULSE = "impulse"
    NOISE_FLOOR_SHIFT = "noise_floor_shift"
    PERIODIC_ACTIVITY = "periodic_activity"
    CONTINUOUS = "continuous"
    WIDEBAND = "wideband"  # Широкополосный сигнал (характерно для дронов с FHSS)
    UNKNOWN = "unknown"


@dataclass
class FrequencyRange:
    """Конфигурация частотного диапазона для мониторинга"""
    name: str
    start_freq: float  # Hz
    stop_freq: float   # Hz
    threshold_db: float = -60.0
    min_duration_ms: float = 100.0
    enabled: bool = True
    
    @property
    def center_freq(self) -> float:
        return (self.start_freq + self.stop_freq) / 2
    
    @property
    def bandwidth(self) -> float:
        return self.stop_freq - self.start_freq
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "start_freq": self.start_freq,
            "stop_freq": self.stop_freq,
            "threshold_db": self.threshold_db,
            "min_duration_ms": self.min_duration_ms,
            "enabled": self.enabled,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FrequencyRange:
        return cls(
            name=data["name"],
            start_freq=float(data["start_freq"]),
            stop_freq=float(data["stop_freq"]),
            threshold_db=float(data.get("threshold_db", -60.0)),
            min_duration_ms=float(data.get("min_duration_ms", 100.0)),
            enabled=bool(data.get("enabled", True)),
        )


@dataclass
class DeviceConfig:
    """Конфигурация SDR устройства"""
    device_type: DeviceType = DeviceType.RTLSDR
    sample_rate: float = 2.0e6
    gain: float = 40.0
    ppm_correction: int = 0
    device_index: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.device_type.value,
            "sample_rate": self.sample_rate,
            "gain": self.gain,
            "ppm_correction": self.ppm_correction,
            "device_index": self.device_index,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceConfig:
        return cls(
            device_type=DeviceType(data.get("type", "rtlsdr")),
            sample_rate=float(data.get("sample_rate", 2.0e6)),
            gain=float(data.get("gain", 40.0)),
            ppm_correction=int(data.get("ppm_correction", 0)),
            device_index=int(data.get("device_index", 0)),
        )


@dataclass
class DetectionConfig:
    """Параметры детекции событий"""
    noise_floor_averaging: int = 100  # количество FFT для усреднения
    impulse_threshold_db: float = 20.0  # превышение над фоном для импульса
    periodic_check_interval: float = 60.0  # секунд
    min_event_gap_ms: float = 500.0  # минимальный интервал между событиями
    fft_size: int = 1024
    overlap: float = 0.5
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "noise_floor_averaging": self.noise_floor_averaging,
            "impulse_threshold_db": self.impulse_threshold_db,
            "periodic_check_interval": self.periodic_check_interval,
            "min_event_gap_ms": self.min_event_gap_ms,
            "fft_size": self.fft_size,
            "overlap": self.overlap,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DetectionConfig:
        return cls(
            noise_floor_averaging=int(data.get("noise_floor_averaging", 100)),
            impulse_threshold_db=float(data.get("impulse_threshold_db", 20.0)),
            periodic_check_interval=float(data.get("periodic_check_interval", 60.0)),
            min_event_gap_ms=float(data.get("min_event_gap_ms", 500.0)),
            fft_size=int(data.get("fft_size", 1024)),
            overlap=float(data.get("overlap", 0.5)),
        )


@dataclass
class OutputConfig:
    """Конфигурация вывода"""
    database_path: Path = field(default_factory=lambda: Path("events.db"))
    log_level: str = "INFO"
    reports_dir: Path = field(default_factory=lambda: Path("reports"))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "database": str(self.database_path),
            "log_level": self.log_level,
            "reports_dir": str(self.reports_dir),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputConfig:
        return cls(
            database_path=Path(data.get("database", "events.db")),
            log_level=data.get("log_level", "INFO"),
            reports_dir=Path(data.get("reports_dir", "reports")),
        )


@dataclass
class AppConfig:
    """Главная конфигурация приложения"""
    device: DeviceConfig = field(default_factory=DeviceConfig)
    ranges: list[FrequencyRange] = field(default_factory=list)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device.to_dict(),
            "ranges": [r.to_dict() for r in self.ranges],
            "detection": self.detection.to_dict(),
            "output": self.output.to_dict(),
        }
    
    def save(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(self.to_dict(), f, default_flow_style=False, allow_unicode=True)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        return cls(
            device=DeviceConfig.from_dict(data.get("device", {})),
            ranges=[FrequencyRange.from_dict(r) for r in data.get("ranges", [])],
            detection=DetectionConfig.from_dict(data.get("detection", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
        )
    
    @classmethod
    def load(cls, path: Path) -> AppConfig:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls.from_dict(data or {})
    
    @classmethod
    def default(cls) -> AppConfig:
        """Создание конфигурации по умолчанию с примером диапазонов"""
        return cls(
            device=DeviceConfig(),
            ranges=[
                FrequencyRange(
                    name="FM Broadcast",
                    start_freq=88e6,
                    stop_freq=108e6,
                    threshold_db=-40.0,
                    min_duration_ms=1000.0,
                ),
            ],
            detection=DetectionConfig(),
            output=OutputConfig(),
        )


@dataclass
class RFEvent:
    """Модель RF-события"""
    id: int | None = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    duration_ms: float = 0.0
    range_name: str = ""
    center_freq: float = 0.0
    bandwidth: float = 0.0
    max_power_db: float = -100.0
    avg_power_db: float = -100.0
    event_type: EventType = EventType.UNKNOWN
    comment: str = ""
    raw_data: bytes | None = None  # для хранения сэмплов события если нужно
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "range_name": self.range_name,
            "center_freq": self.center_freq,
            "bandwidth": self.bandwidth,
            "max_power_db": self.max_power_db,
            "avg_power_db": self.avg_power_db,
            "event_type": self.event_type.value,
            "comment": self.comment,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RFEvent:
        return cls(
            id=data.get("id"),
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            duration_ms=float(data.get("duration_ms", 0.0)),
            range_name=data.get("range_name", ""),
            center_freq=float(data.get("center_freq", 0.0)),
            bandwidth=float(data.get("bandwidth", 0.0)),
            max_power_db=float(data.get("max_power_db", -100.0)),
            avg_power_db=float(data.get("avg_power_db", -100.0)),
            event_type=EventType(data.get("event_type", "unknown")),
            comment=data.get("comment", ""),
        )
    
    def generate_comment(self) -> str:
        """Автоматическая генерация комментария к событию"""
        freq_mhz = self.center_freq / 1e6
        
        type_descriptions = {
            EventType.THRESHOLD_EXCEEDED: "Превышение порога",
            EventType.IMPULSE: "Импульсная помеха",
            EventType.NOISE_FLOOR_SHIFT: "Изменение уровня шума",
            EventType.PERIODIC_ACTIVITY: "Периодическая активность",
            EventType.CONTINUOUS: "Непрерывное излучение",
            EventType.UNKNOWN: "Неклассифицированное событие",
        }
        
        type_desc = type_descriptions.get(self.event_type, "Событие")
        
        comment = f"{type_desc} на {freq_mhz:.3f} МГц. "
        comment += f"Макс. уровень: {self.max_power_db:.1f} дБ. "
        
        if self.duration_ms < 1000:
            comment += f"Длительность: {self.duration_ms:.0f} мс."
        else:
            comment += f"Длительность: {self.duration_ms / 1000:.1f} с."
        
        return comment
