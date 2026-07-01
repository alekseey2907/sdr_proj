"""Единый модуль безопасности SkyShield.

Содержит проверку токена устройства для приема телеметрии/алертов и
HTTP Basic аутентификацию для админ-страницы настроек.

Поведение обратно совместимо: если токен/пароль не заданы, доступ разрешается,
но выводится предупреждение. Для проданных устройств значения задаются в
/etc/skyshield/skyshield.env и /etc/skyshield/device.json.
"""

import json
import logging
import os
import secrets
from pathlib import Path

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

logger = logging.getLogger(__name__)

_DEVICE_IDENTITY_PATHS = (
    os.getenv("DEVICE_IDENTITY_PATH", ""),
    "/etc/skyshield/device.json",
    "backend/data/device.json",
)

_warned_no_device_token = False
_warned_no_admin = False


def _load_identity_token() -> str:
    for raw_path in _DEVICE_IDENTITY_PATHS:
        if not raw_path:
            continue
        path = Path(raw_path)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                token = str(data.get("device_token", "")).strip()
                if token:
                    return token
        except (OSError, json.JSONDecodeError):
            continue
    return ""


def get_expected_device_token() -> str:
    """Ожидаемый токен устройства: сперва env, затем device.json."""
    token = (os.getenv("DEVICE_TOKEN") or "").strip()
    if token:
        return token
    return _load_identity_token()


async def require_device_token(x_device_token: str | None = Header(default=None)) -> None:
    """Зависимость FastAPI: проверяет заголовок X-Device-Token.

    Если токен на устройстве не настроен — пропускает (с предупреждением),
    чтобы не ломать существующие развертывания до миграции.
    """
    global _warned_no_device_token
    expected = get_expected_device_token()
    if not expected:
        if not _warned_no_device_token:
            logger.warning(
                "DEVICE_TOKEN не настроен — прием телеметрии открыт. "
                "Задайте DEVICE_TOKEN в skyshield.env для продакшена."
            )
            _warned_no_device_token = True
        return

    provided = (x_device_token or "").strip()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing device token",
        )


_basic = HTTPBasic(auto_error=False)


async def require_admin(
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> None:
    """HTTP Basic для админ-страницы настроек.

    Если пароль не задан в env — доступ открыт (с предупреждением).
    """
    global _warned_no_admin
    admin_user = (os.getenv("SKYSHIELD_ADMIN_USER") or "").strip()
    admin_password = (os.getenv("SKYSHIELD_ADMIN_PASSWORD") or "").strip()

    if not admin_password:
        if not _warned_no_admin:
            logger.warning(
                "SKYSHIELD_ADMIN_PASSWORD не задан — /settings открыт. "
                "Задайте пароль в skyshield.env для продакшена."
            )
            _warned_no_admin = True
        return

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(credentials.username, admin_user or credentials.username)
    password_ok = secrets.compare_digest(credentials.password, admin_password)
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
