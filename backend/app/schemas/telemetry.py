from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class DeviceStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class NarrowbandSpectrumData(BaseModel):
    start_mhz: float = Field(..., description="Начало диапазона")
    stop_mhz: float = Field(..., description="Конец диапазона")
    freqs_mhz: list[float] = Field(..., description="Частотная ось")
    bins: list[float] = Field(..., description="Уровни спектра в dB")
    peak_detected: bool = Field(default=False, description="Обнаружен ли пик выше фона")
    peak_freq_mhz: Optional[float] = Field(default=None, description="Частота пика")
    peak_power_dbm: Optional[float] = Field(default=None, description="Мощность пика")
    noise_floor_dbm: Optional[float] = Field(default=None, description="Оценка шумового пола")
    peak_delta_db: Optional[float] = Field(default=None, description="Отрыв пика от шумового пола")
    active_ratio: Optional[float] = Field(default=None, description="Доля бинов выше порога активности")
    occupied_bw_mhz: Optional[float] = Field(default=None, description="Оценка занятой полосы")
    mean_excess_db: Optional[float] = Field(default=None, description="Среднее превышение активных бинов над шумом")


class SpectrumData(BaseModel):
    bins: list[float] = Field(..., description="Полосы спектра (868/1280 МГц)")
    narrowband_868_870: Optional[NarrowbandSpectrumData] = Field(
        default=None,
        description="Узкополосный live-спектр 868-870 МГц",
    )
    narrowband_1279_1281: Optional[NarrowbandSpectrumData] = Field(
        default=None,
        description="Узкополосный live-спектр 1279-1281 МГц",
    )

class TelemetryMetrics(BaseModel):
    velocity_rms_mm_s: float = Field(..., ge=0, description="Среднеквадратичная скорость вибрации")
    accel_peak_g: float = Field(..., ge=0, description="Пиковое ускорение")
    crest_factor: float = Field(..., ge=0, description="Пик-фактор")
    temperature_c: float = Field(..., description="Температура")
    dominant_freq_hz: float = Field(..., ge=0, description="Доминантная частота")

class TelemetryBase(BaseModel):
    device_id: str = Field(..., min_length=1, description="MAC адрес или ID устройства")
    # timezone-aware UTC timestamp by default (prevents JS Date parsing ambiguity)
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: DeviceStatus

class TelemetryCreate(TelemetryBase):
    metrics: TelemetryMetrics
    spectrum: SpectrumData

class TelemetryResponse(TelemetryBase):
    id: int
    metrics: TelemetryMetrics
    spectrum: SpectrumData
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
