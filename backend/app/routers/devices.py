"""Эндпоинт идентичности устройства для парковой инвентаризации.

Локальный backend автономен, поэтому здесь отдается информация только о
текущем устройстве. Централизованный реестр парка собирается на стороне
вендора скриптом scripts/collect_inventory.* через SSH.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from app.security import require_admin

router = APIRouter(prefix="/api/v1/device", tags=["device"])

_IDENTITY_PATHS = (
    os.getenv("DEVICE_IDENTITY_PATH", ""),
    "/etc/skyshield/device.json",
    "backend/data/device.json",
)

_VERSION_PATHS = (
    os.getenv("SKYSHIELD_VERSION_PATH", ""),
    "VERSION",
    "/opt/skyshield/sdr_proj/VERSION",
)


def _read_device_id() -> str:
    env_id = (os.getenv("DEVICE_ID") or "").strip()
    if env_id:
        return env_id
    for raw_path in _IDENTITY_PATHS:
        if not raw_path:
            continue
        path = Path(raw_path)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                device_id = str(data.get("device_id", "")).strip()
                if device_id:
                    return device_id
        except (OSError, json.JSONDecodeError):
            continue
    return "unknown"


def _read_version() -> str:
    for raw_path in _VERSION_PATHS:
        if not raw_path:
            continue
        path = Path(raw_path)
        try:
            if path.exists():
                version = path.read_text(encoding="utf-8").strip()
                if version:
                    return version
        except OSError:
            continue
    return "unknown"


@router.get("/info")
async def device_info(_admin: None = Depends(require_admin)):
    return {
        "device_id": _read_device_id(),
        "version": _read_version(),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
