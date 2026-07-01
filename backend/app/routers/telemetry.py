import json
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.database import AsyncSessionLocal, get_db
from app.models.telemetry import Telemetry
from app.schemas.telemetry import TelemetryCreate, TelemetryResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/telemetry",
    tags=["telemetry"]
)


NARROWBAND_KEYS = (
    "narrowband_868_870",
    "narrowband_1279_1281",
)

LATEST_TELEMETRY: dict[str, TelemetryResponse] = {}
LAST_HISTORY_WRITE_AT: dict[str, float] = {}
TELEMETRY_HISTORY_INTERVAL_SECONDS = float(os.getenv("TELEMETRY_HISTORY_INTERVAL_SECONDS", "10"))
_CACHE_ID = 0


def _coerce_float_list(values):
    if not isinstance(values, list):
        return []

    result = []
    for value in values:
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            continue
    return result


def _normalize_narrowband_payload(payload):
    if not isinstance(payload, dict):
        return None

    freqs = _coerce_float_list(payload.get("freqs_mhz"))
    bins = _coerce_float_list(payload.get("bins"))
    if not freqs or not bins:
        return None

    try:
        start_mhz = float(payload.get("start_mhz"))
        stop_mhz = float(payload.get("stop_mhz"))
    except (TypeError, ValueError):
        return None

    normalized = {
        "start_mhz": start_mhz,
        "stop_mhz": stop_mhz,
        "freqs_mhz": freqs,
        "bins": bins,
        "peak_detected": bool(payload.get("peak_detected", False)),
        "peak_freq_mhz": payload.get("peak_freq_mhz"),
        "peak_power_dbm": payload.get("peak_power_dbm"),
        "noise_floor_dbm": payload.get("noise_floor_dbm"),
        "peak_delta_db": payload.get("peak_delta_db"),
        "active_ratio": payload.get("active_ratio"),
        "occupied_bw_mhz": payload.get("occupied_bw_mhz"),
        "mean_excess_db": payload.get("mean_excess_db"),
    }

    for key in (
        "peak_freq_mhz",
        "peak_power_dbm",
        "noise_floor_dbm",
        "peak_delta_db",
        "active_ratio",
        "occupied_bw_mhz",
        "mean_excess_db",
    ):
        value = normalized[key]
        if value is None:
            continue
        try:
            normalized[key] = float(value)
        except (TypeError, ValueError):
            normalized[key] = None

    return normalized


def _serialize_spectrum(spectrum_value):
    if isinstance(spectrum_value, str):
        try:
            spectrum_value = json.loads(spectrum_value)
        except json.JSONDecodeError:
            spectrum_value = None

    if isinstance(spectrum_value, dict):
        bins = _coerce_float_list(spectrum_value.get("bins"))
        normalized = {"bins": bins}
        for key in NARROWBAND_KEYS:
            normalized[key] = _normalize_narrowband_payload(spectrum_value.get(key))
        return normalized

    return {"bins": _coerce_float_list(spectrum_value)}


def _normalize_status(status_value):
    value = str(status_value or "OK").upper()
    if value in {"OK", "WARNING", "CRITICAL"}:
        return value
    return "OK"


def _build_telemetry_response(item: Telemetry) -> TelemetryResponse:
    return TelemetryResponse(
        device_id=item.device_id,
        timestamp=item.timestamp or datetime.now(timezone.utc),
        status=_normalize_status(item.status),
        metrics={
            "velocity_rms_mm_s": float(item.velocity_rms_mm_s or 0.0),
            "accel_peak_g": float(item.accel_peak_g or 0.0),
            "crest_factor": float(item.crest_factor or 0.0),
            "temperature_c": float(item.temperature_c or 0.0),
            "dominant_freq_hz": float(item.dominant_freq_hz or 0.0),
        },
        spectrum=_serialize_spectrum(item.spectrum_bins),
        id=item.id,
        created_at=item.created_at or item.timestamp or datetime.now(timezone.utc),
    )


def _build_live_telemetry_response(data: TelemetryCreate) -> TelemetryResponse:
    global _CACHE_ID

    _CACHE_ID += 1
    now = datetime.now(timezone.utc)
    return TelemetryResponse(
        device_id=data.device_id,
        timestamp=data.timestamp or now,
        status=data.status,
        metrics=data.metrics,
        spectrum=data.spectrum,
        id=_CACHE_ID,
        created_at=now,
    )


async def _persist_telemetry(data: TelemetryCreate) -> None:
    try:
        async with AsyncSessionLocal() as db:
            db_item = Telemetry(
                device_id=data.device_id,
                timestamp=data.timestamp,
                velocity_rms_mm_s=data.metrics.velocity_rms_mm_s,
                accel_peak_g=data.metrics.accel_peak_g,
                crest_factor=data.metrics.crest_factor,
                temperature_c=data.metrics.temperature_c,
                dominant_freq_hz=data.metrics.dominant_freq_hz,
                spectrum_bins=data.spectrum.model_dump(),
                status=data.status.value,
            )
            db.add(db_item)
            await db.commit()
    except SQLAlchemyError as exc:
        logger.warning("Telemetry history write skipped: %s", exc)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_telemetry(data: TelemetryCreate, background_tasks: BackgroundTasks):
    """
    Прием телеметрии от ESP32
    """
    response = _build_live_telemetry_response(data)
    LATEST_TELEMETRY[data.device_id] = response

    now = time.monotonic()
    last_write_at = LAST_HISTORY_WRITE_AT.get(data.device_id, 0.0)
    if TELEMETRY_HISTORY_INTERVAL_SECONDS <= 0 or now - last_write_at >= TELEMETRY_HISTORY_INTERVAL_SECONDS:
        LAST_HISTORY_WRITE_AT[data.device_id] = now
        background_tasks.add_task(_persist_telemetry, data)

    return response

@router.get("/{device_id}/latest", response_model=TelemetryResponse)
async def get_latest_telemetry(device_id: str, db: AsyncSession = Depends(get_db)):
    """
    Получить последнее состояние устройства
    """
    cached = LATEST_TELEMETRY.get(device_id)
    if cached is not None:
        return cached

    query = select(Telemetry).where(Telemetry.device_id == device_id).order_by(desc(Telemetry.timestamp)).limit(1)
    result = await db.execute(query)
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(status_code=404, detail="Device not found")
        
    return _build_telemetry_response(item)

@router.get("/{device_id}", response_model=list[TelemetryResponse])
async def get_device_history(
    device_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    История измерений устройства (последние N точек, в хронологическом порядке).

    По умолчанию возвращаем последние записи (а не самые старые),
    чтобы графики после обновления страницы выглядели стабильно.
    """
    query = (
        select(Telemetry)
        .where(Telemetry.device_id == device_id)
        .order_by(desc(Telemetry.timestamp))
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    items = result.scalars().all()

    # Превращаем (latest..oldest) -> (oldest..latest)
    items.reverse()
    
    return [
        _build_telemetry_response(item)
        for item in items
    ]
