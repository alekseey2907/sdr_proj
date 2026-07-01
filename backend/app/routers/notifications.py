import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.security import require_admin, require_device_token

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])

SETTINGS_PATH = Path(
    os.getenv(
        "NOTIFICATION_SETTINGS_PATH",
        "/etc/skyshield/notification_settings.json" if os.name != "nt" else "backend/data/notification_settings.json",
    )
)

_settings_lock = threading.RLock()
_last_alert_at: dict[str, float] = {}


class AlertPayload(BaseModel):
    source: str = Field(..., min_length=1, description="rf или acoustic")
    level: float | None = Field(default=None, description="Уровень/уверенность 0-100")
    title: str | None = None
    message: str | None = None
    frequency_mhz: float | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class NotificationSettingsUpdate(BaseModel):
    vk_enabled: bool = True
    vk_bot_token: str | None = None
    vk_peer_ids: list[str] | str = Field(default_factory=list)
    vk_api_version: str = "5.131"
    rf_enabled: bool = True
    rf_cooldown_seconds: int = Field(default=0, ge=0)
    acoustic_enabled: bool = True
    acoustic_cooldown_seconds: int = Field(default=0, ge=0)


def _split_peer_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = value.replace(";", ",").replace("\n", ",").split(",")
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []

    result = []
    seen = set()
    for item in raw_items:
        peer_id = str(item).strip()
        if not peer_id or peer_id in seen:
            continue
        result.append(peer_id)
        seen.add(peer_id)
    return result


def _default_settings() -> dict[str, Any]:
    return {
        "vk": {
            "enabled": True,
            "bot_token": os.getenv("VK_BOT_TOKEN", ""),
            "peer_ids": _split_peer_ids(os.getenv("VK_PEER_ID", "")),
            "api_version": os.getenv("VK_API_VERSION", "5.131"),
        },
        "sources": {
            "rf": {
                "enabled": True,
                "cooldown_seconds": 0,
                "label": "SkyShield RF",
            },
            "acoustic": {
                "enabled": True,
                "cooldown_seconds": 0,
                "label": "SkyShield Acoustic",
            },
        },
    }


def _deep_merge(default: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(default))
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_settings() -> dict[str, Any]:
    default = _default_settings()
    with _settings_lock:
        if not SETTINGS_PATH.exists():
            return default
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Notification settings load failed: %s", exc)
            return default
        if not isinstance(loaded, dict):
            return default
        return _deep_merge(default, loaded)


def _save_settings(settings: dict[str, Any]) -> None:
    with _settings_lock:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = SETTINGS_PATH.with_suffix(SETTINGS_PATH.suffix + ".tmp")
        tmp_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(SETTINGS_PATH)


def _mask_token(token: str) -> str:
    if not token:
        return ""
    if len(token) <= 12:
        return "*" * len(token)
    return f"{token[:6]}...{token[-6:]}"


def _public_settings(settings: dict[str, Any]) -> dict[str, Any]:
    vk = settings.get("vk", {})
    sources = settings.get("sources", {})
    return {
        "settings_path": str(SETTINGS_PATH),
        "vk_enabled": bool(vk.get("enabled", True)),
        "vk_bot_token_configured": bool(vk.get("bot_token")),
        "vk_bot_token_masked": _mask_token(str(vk.get("bot_token", ""))),
        "vk_peer_ids": _split_peer_ids(vk.get("peer_ids", [])),
        "vk_api_version": str(vk.get("api_version", "5.131")),
        "rf_enabled": bool(sources.get("rf", {}).get("enabled", True)),
        "rf_cooldown_seconds": int(sources.get("rf", {}).get("cooldown_seconds", 0)),
        "acoustic_enabled": bool(sources.get("acoustic", {}).get("enabled", True)),
        "acoustic_cooldown_seconds": int(sources.get("acoustic", {}).get("cooldown_seconds", 0)),
    }


def _source_settings(settings: dict[str, Any], source: str) -> dict[str, Any]:
    sources = settings.get("sources", {})
    return sources.get(source, {"enabled": True, "cooldown_seconds": 0, "label": source})


def _format_alert_message(payload: AlertPayload, source_config: dict[str, Any]) -> str:
    if payload.message:
        return payload.message

    label = source_config.get("label") or payload.source.upper()
    title = payload.title or "ТРЕВОГА! ОБНАРУЖЕН ДРОН!"
    lines = [f"🚨 {title}", "", f"Источник: {label}"]

    if payload.level is not None:
        lines.append(f"Уровень: {payload.level:.1f}%")
    if payload.frequency_mhz is not None:
        lines.append(f"Диапазон: {payload.frequency_mhz:.3f} MHz")

    for key, value in payload.details.items():
        if value is None or value == "":
            continue
        lines.append(f"{key}: {value}")

    lines.append("Совет: проверьте обстановку и укрытие.")
    return "\n".join(lines)


def _send_vk_message(token: str, peer_id: str, api_version: str, message: str) -> bool:
    payload = urllib.parse.urlencode(
        {
            "access_token": token,
            "peer_id": peer_id,
            "random_id": int(time.time() * 1000) % 2147483647,
            "message": message,
            "v": api_version,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        "https://api.vk.com/method/messages.send",
        data=payload,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning("VK send failed for peer %s: %s", peer_id, exc)
        return False

    if "error" in result:
        logger.warning("VK API error for peer %s: %s", peer_id, result["error"])
        return False
    return True


def _send_vk_to_all(message: str, settings: dict[str, Any]) -> None:
    vk = settings.get("vk", {})
    if not vk.get("enabled", True):
        return

    token = str(vk.get("bot_token", ""))
    peer_ids = _split_peer_ids(vk.get("peer_ids", []))
    api_version = str(vk.get("api_version", "5.131"))
    if not token or not peer_ids:
        logger.warning("VK notification skipped: token or peer_ids are empty")
        return

    for peer_id in peer_ids:
        _send_vk_message(token, peer_id, api_version, message)


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(_admin: None = Depends(require_admin)):
    return HTMLResponse(
        """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SkyShield — Settings</title>
    <style>
        :root { --bg:#0d1117; --panel:#161b22; --line:#30363d; --text:#e6edf3; --muted:#8b949e; --ok:#2ea043; --warn:#d29922; }
        body { margin:0; padding:24px; background:var(--bg); color:var(--text); font-family:Segoe UI, sans-serif; }
        .wrap { max-width: 920px; margin: 0 auto; }
        .top { display:flex; justify-content:space-between; align-items:center; gap:16px; margin-bottom:22px; }
        h1 { margin:0; font-size:24px; }
        a { color:#79c0ff; text-decoration:none; }
        .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:20px; margin-bottom:16px; }
        label { display:block; color:var(--muted); font-size:13px; margin:14px 0 6px; }
        input, textarea { box-sizing:border-box; width:100%; background:#0d1117; border:1px solid var(--line); border-radius:6px; color:var(--text); padding:10px 12px; font-size:15px; }
        input[type="checkbox"] { width:auto; margin-right:8px; }
        .grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        .row { display:flex; align-items:center; gap:8px; margin-top:12px; color:var(--muted); }
        .hint { color:var(--muted); font-size:13px; margin-top:8px; }
        .actions { display:flex; gap:12px; align-items:center; margin-top:18px; flex-wrap:wrap; }
        button { background:var(--ok); color:white; border:0; border-radius:6px; padding:10px 14px; font-weight:700; cursor:pointer; }
        button.secondary { background:#21262d; border:1px solid var(--line); }
        #status { color:var(--warn); }
        @media (max-width: 700px) { .grid { grid-template-columns:1fr; } body { padding:14px; } }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="top">
            <h1>SkyShield Settings</h1>
            <a href="/dashboard">Открыть RF</a>
        </div>
        <div class="panel">
            <h2>VK Bot</h2>
            <div class="row"><input id="vk_enabled" type="checkbox"><span>VK уведомления включены</span></div>
            <label for="vk_bot_token">VK bot token</label>
            <input id="vk_bot_token" type="password" autocomplete="off" placeholder="Оставьте пустым, чтобы не менять текущий токен">
            <div class="hint" id="token_hint"></div>
            <label for="vk_peer_ids">VK peer/user IDs</label>
            <textarea id="vk_peer_ids" rows="4" placeholder="Один или несколько ID через запятую или с новой строки"></textarea>
            <label for="vk_api_version">VK API version</label>
            <input id="vk_api_version" type="text" value="5.131">
        </div>
        <div class="panel">
            <h2>Sources</h2>
            <div class="grid">
                <div>
                    <div class="row"><input id="rf_enabled" type="checkbox"><span>RF алерты включены</span></div>
                    <label for="rf_cooldown_seconds">RF cooldown, сек</label>
                    <input id="rf_cooldown_seconds" type="number" min="0" step="1">
                </div>
                <div>
                    <div class="row"><input id="acoustic_enabled" type="checkbox"><span>Акустические алерты включены</span></div>
                    <label for="acoustic_cooldown_seconds">Acoustic cooldown, сек</label>
                    <input id="acoustic_cooldown_seconds" type="number" min="0" step="1">
                </div>
            </div>
            <div class="actions">
                <button onclick="saveSettings()">Сохранить</button>
                <button class="secondary" onclick="sendTest()">Тест VK</button>
                <span id="statusMsg"></span>
            </div>
        </div>
    </div>
    <script>
        const api = '/api/v1/notifications/settings';
        const statusEl = document.getElementById('statusMsg');
        function setStatus(text) { statusEl.textContent = text; }
        function peersText(value) { return Array.isArray(value) ? value.join('\\n') : ''; }
        async function loadSettings() {
            const response = await fetch(api);
            if (!response.ok) { setStatus('Ошибка загрузки настроек (' + response.status + ')'); return; }
            const data = await response.json();
            document.getElementById('vk_enabled').checked = !!data.vk_enabled;
            document.getElementById('vk_peer_ids').value = peersText(data.vk_peer_ids);
            document.getElementById('vk_api_version').value = data.vk_api_version || '5.131';
            document.getElementById('rf_enabled').checked = !!data.rf_enabled;
            document.getElementById('rf_cooldown_seconds').value = data.rf_cooldown_seconds ?? 0;
            document.getElementById('acoustic_enabled').checked = !!data.acoustic_enabled;
            document.getElementById('acoustic_cooldown_seconds').value = data.acoustic_cooldown_seconds ?? 0;
            document.getElementById('token_hint').textContent = data.vk_bot_token_configured
                ? ('Токен задан: ' + (data.vk_bot_token_masked || '***'))
                : 'Токен не задан — введите ниже';
        }
        async function saveSettings() {
            setStatus('Сохраняю...');
            const payload = {
                vk_enabled: document.getElementById('vk_enabled').checked,
                vk_bot_token: document.getElementById('vk_bot_token').value,
                vk_peer_ids: document.getElementById('vk_peer_ids').value,
                vk_api_version: document.getElementById('vk_api_version').value,
                rf_enabled: document.getElementById('rf_enabled').checked,
                rf_cooldown_seconds: Number(document.getElementById('rf_cooldown_seconds').value || 0),
                acoustic_enabled: document.getElementById('acoustic_enabled').checked,
                acoustic_cooldown_seconds: Number(document.getElementById('acoustic_cooldown_seconds').value || 0),
            };
            try {
                const response = await fetch(api, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
                if (!response.ok) { setStatus('Ошибка сохранения (' + response.status + ')'); return; }
                document.getElementById('vk_bot_token').value = '';
                setStatus('✅ Сохранено');
                await loadSettings();
            } catch (err) { setStatus('Ошибка: ' + err.message); }
        }
        async function sendTest() {
            setStatus('Отправляю тест...');
            try {
                const response = await fetch('/api/v1/notifications/test', { method: 'POST' });
                const data = await response.json().catch(() => ({}));
                if (response.ok) {
                    setStatus('✅ Тест отправлен (' + (data.peer_count || '?') + ' получателей)');
                } else {
                    setStatus('❌ ' + (data.detail || 'Ошибка теста'));
                }
            } catch (err) { setStatus('❌ Ошибка: ' + err.message); }
        }
        loadSettings().catch(err => setStatus('Ошибка загрузки: ' + err.message));
    </script>
</body>
</html>
        """
    )


@router.get("/api/v1/notifications/settings")
async def get_notification_settings(_admin: None = Depends(require_admin)):
    return _public_settings(_load_settings())


@router.post("/api/v1/notifications/settings")
async def update_notification_settings(
    payload: NotificationSettingsUpdate,
    _admin: None = Depends(require_admin),
):
    settings = _load_settings()
    vk = settings.setdefault("vk", {})
    sources = settings.setdefault("sources", {})

    vk["enabled"] = payload.vk_enabled
    new_token = (payload.vk_bot_token or "").strip()
    if new_token:
        vk["bot_token"] = new_token
    vk["peer_ids"] = _split_peer_ids(payload.vk_peer_ids)
    vk["api_version"] = payload.vk_api_version.strip() or "5.131"

    sources["rf"] = {
        "enabled": payload.rf_enabled,
        "cooldown_seconds": payload.rf_cooldown_seconds,
        "label": "SkyShield RF",
    }
    sources["acoustic"] = {
        "enabled": payload.acoustic_enabled,
        "cooldown_seconds": payload.acoustic_cooldown_seconds,
        "label": "SkyShield Acoustic",
    }

    _save_settings(settings)
    return _public_settings(settings)


@router.post("/api/v1/notifications/alert")
async def receive_alert(
    payload: AlertPayload,
    background_tasks: BackgroundTasks,
    _auth: None = Depends(require_device_token),
):
    settings = _load_settings()
    source = payload.source.strip().lower()
    source_config = _source_settings(settings, source)
    if not source_config.get("enabled", True):
        return {"accepted": False, "reason": "source_disabled", "source": source}

    cooldown = max(0, int(source_config.get("cooldown_seconds", 0)))
    now = time.monotonic()
    last_alert_at = _last_alert_at.get(source, 0.0)
    remaining = cooldown - (now - last_alert_at)
    if remaining > 0:
        return {"accepted": False, "reason": "cooldown", "source": source, "retry_after_seconds": round(remaining, 1)}

    vk = settings.get("vk", {})
    if not vk.get("enabled", True):
        return {"accepted": False, "reason": "vk_disabled", "source": source}
    if not vk.get("bot_token") or not _split_peer_ids(vk.get("peer_ids", [])):
        return {"accepted": False, "reason": "vk_not_configured", "source": source}

    _last_alert_at[source] = now
    message = _format_alert_message(payload, source_config)
    background_tasks.add_task(_send_vk_to_all, message, settings)
    return {"accepted": True, "source": source, "peer_count": len(_split_peer_ids(vk.get("peer_ids", [])))}


@router.post("/api/v1/notifications/test")
async def send_test_notification(
    background_tasks: BackgroundTasks,
    _admin: None = Depends(require_admin),
):
    settings = _load_settings()
    vk = settings.get("vk", {})
    if not vk.get("bot_token") or not _split_peer_ids(vk.get("peer_ids", [])):
        raise HTTPException(status_code=400, detail="VK token or peer_ids are not configured")
    background_tasks.add_task(_send_vk_to_all, "SkyShield test notification", settings)
    return {"ok": True, "peer_count": len(_split_peer_ids(vk.get("peer_ids", [])))}