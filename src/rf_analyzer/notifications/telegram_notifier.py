"""
RF Event Analyzer - Telegram Notifications
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from queue import Empty, Queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rf_analyzer.core.config import RFEvent

logger = logging.getLogger(__name__)


@dataclass
class TelegramConfig:
    """Конфигурация Telegram бота"""
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    notify_on_event: bool = True
    notify_on_error: bool = True
    min_power_db: float = -50.0  # Минимальный уровень для уведомления
    cooldown_seconds: int = 5  # Быстрая реакция для обнаружения дронов
    
    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "notify_on_event": self.notify_on_event,
            "notify_on_error": self.notify_on_error,
            "min_power_db": self.min_power_db,
            "cooldown_seconds": self.cooldown_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> TelegramConfig:
        return cls(
            enabled=data.get("enabled", False),
            bot_token=data.get("bot_token", ""),
            chat_id=data.get("chat_id", ""),
            notify_on_event=data.get("notify_on_event", True),
            notify_on_error=data.get("notify_on_error", True),
            min_power_db=data.get("min_power_db", -50.0),
            cooldown_seconds=data.get("cooldown_seconds", 60),
        )


class TelegramNotifier:
    """Отправка уведомлений в Telegram"""
    
    API_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, config: TelegramConfig):
        self.config = config
        self._queue: Queue = Queue()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        # cooldown применяем только к событиям и отдельно по ключу, чтобы разные частоты/диапазоны
        # не "глушили" друг друга
        self._last_event_notification: dict[str, datetime] = {}
        # чтобы не забивать очередь, пока сообщение ещё не отправлено
        self._pending_event_keys: set[str] = set()
        self._running = False
    
    def start(self) -> bool:
        """Запустить сервис уведомлений"""
        if not self.config.enabled:
            logger.info("Telegram notifications disabled")
            return False
        
        if not self.config.bot_token or not self.config.chat_id:
            logger.warning("Telegram bot_token or chat_id not configured")
            return False
        
        self._stop_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()
        
        logger.info("Telegram notifier started")
        return True
    
    def stop(self) -> None:
        """Остановить сервис"""
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("Telegram notifier stopped")
    
    def notify_event(self, event: RFEvent) -> None:
        """Уведомить о событии"""
        logger.debug(f"notify_event called: running={self._running}, notify_on_event={self.config.notify_on_event}")
        
        if not self._running:
            logger.debug("Telegram notifier not running")
            return
            
        if not self.config.notify_on_event:
            logger.debug("Event notifications disabled in config")
            return
        
        # Проверяем минимальный уровень
        if event.max_power_db < self.config.min_power_db:
            logger.debug(f"Event power {event.max_power_db:.1f} dB below threshold {self.config.min_power_db:.1f} dB")
            return
        
        # Проверяем cooldown (по ключу события, а не глобально)
        cooldown_key = self._event_cooldown_key(event)

        # Уже ждём отправку по этому ключу — не дублируем
        if cooldown_key in self._pending_event_keys:
            logger.debug(f"Telegram send pending for {cooldown_key}")
            return

        last_time = self._last_event_notification.get(cooldown_key)
        if last_time:
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < self.config.cooldown_seconds:
                logger.debug(
                    f"Cooldown active for {cooldown_key}: {elapsed:.1f}s / {self.config.cooldown_seconds}s"
                )
                return
        
        logger.info(f"Sending Telegram notification for event at {event.center_freq/1e6:.3f} MHz, power={event.max_power_db:.1f} dB")
        message = self._format_event_message(event)
        # передаём ключ, чтобы обновить cooldown только при успешной отправке
        self._pending_event_keys.add(cooldown_key)
        self._queue.put(("event", message, cooldown_key))
    
    def notify_error(self, error: str) -> None:
        """Уведомить об ошибке"""
        if not self._running or not self.config.notify_on_error:
            return
        
        message = f"⚠️ *RF Analyzer Error*\n\n{error}"
        self._queue.put(("error", message, None))
    
    def notify_status(self, status: str) -> None:
        """Уведомить о статусе"""
        if not self._running:
            return

        self._queue.put(("status", status, None))
    
    def test_connection(self) -> tuple[bool, str]:
        """Проверить подключение к боту"""
        try:
            result = self._api_call("getMe")
            if result and result.get("ok"):
                bot_name = result.get("result", {}).get("username", "Unknown")
                return True, f"Connected to @{bot_name}"
            return False, "Invalid response from Telegram API"
        except Exception as e:
            return False, str(e)
    
    def _format_event_message(self, event: RFEvent) -> str:
        """Форматировать сообщение о событии"""
        freq_mhz = event.center_freq / 1e6
        
        # Эмодзи по типу события
        type_emoji = {
            "threshold_exceeded": "📶",
            "impulse": "⚡",
            "noise_floor_shift": "📊",
            "periodic_activity": "🔄",
            "continuous": "📻",
        }
        emoji = type_emoji.get(event.event_type.value, "📡")
        
        # Перевод типов событий на русский
        type_names = {
            "threshold_exceeded": "Превышение порога",
            "impulse": "Импульс",
            "noise_floor_shift": "Сдвиг шума",
            "periodic_activity": "Периодическая активность",
            "continuous": "Непрерывный сигнал",
        }
        type_name = type_names.get(event.event_type.value, event.event_type.value)
        
        # Текущее время отправки уведомления
        from datetime import datetime
        current_time = datetime.now()
        
        # Сообщение на русском языке
        message = f"{emoji} Обнаружено RF событие\n\n"
        message += f"📍 Диапазон: {event.range_name}\n"
        message += f"📻 Частота: {freq_mhz:.3f} МГц\n"
        message += f"📈 Мощность: {event.max_power_db:.1f} дБ\n"
        message += f"⏱ Длительность: {event.duration_ms:.0f} мс\n"
        message += f"🏷 Тип: {type_name}\n"
        message += f"🕐 Начало: {event.start_time.strftime('%H:%M:%S')}\n"
        message += f"📤 Отправлено: {current_time.strftime('%H:%M:%S')}"
        
        return message

    def _event_cooldown_key(self, event: RFEvent) -> str:
        # Округляем частоту до 1 кГц, чтобы микросмещения не обходили cooldown
        freq_khz = int(round(event.center_freq / 1e3))
        return f"{event.range_name}|{freq_khz}kHz|{event.event_type.value}"
    
    def _worker(self) -> None:
        """Рабочий поток отправки"""
        logger.info("Telegram worker thread started")
        while not self._stop_event.is_set():
            try:
                msg_type, message, cooldown_key = self._queue.get(timeout=1.0)
                logger.info(f"Sending Telegram message (type={msg_type})")
                if self._send_with_retries(message):
                    logger.info("Telegram message sent successfully")
                    if cooldown_key:
                        self._last_event_notification[cooldown_key] = datetime.now()
                        self._pending_event_keys.discard(cooldown_key)
                else:
                    logger.error("Failed to send Telegram message (giving up)")
                    if cooldown_key:
                        self._pending_event_keys.discard(cooldown_key)
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Telegram worker error: {e}")

    def _send_with_retries(self, text: str) -> bool:
        """Отправить сообщение с повторными попытками (устойчиво к временным сетевым сбоям)."""
        max_attempts = 5
        base_delay = 1.0
        for attempt in range(1, max_attempts + 1):
            if self._stop_event.is_set():
                return False

            ok, retry_after, err = self._send_message(text)
            if ok:
                return True

            if attempt >= max_attempts:
                if err:
                    logger.error(f"Telegram send failed after {attempt} attempts: {err}")
                return False

            delay = retry_after if retry_after is not None else min(base_delay * (2 ** (attempt - 1)), 30.0)
            logger.warning(
                f"Telegram send failed (attempt {attempt}/{max_attempts}): {err or 'unknown error'}. "
                f"Retry in {delay:.1f}s"
            )
            time.sleep(delay)
        return False
    
    def _send_message(self, text: str) -> tuple[bool, float | None, str | None]:
        """Отправить сообщение.

        Returns:
            (ok, retry_after_seconds, error_message)
        """
        try:
            result = self._api_call(
                "sendMessage",
                {
                    "chat_id": self.config.chat_id,
                    "text": text,
                    # Без parse_mode - отправляем простой текст
                },
            )
            if not result:
                return False, None, "empty response"

            if result.get("ok"):
                return True, None, None

            # Telegram может вернуть 429 Too Many Requests с retry_after
            error_code = result.get("error_code")
            description = result.get("description")
            retry_after = None
            try:
                params = result.get("parameters") or {}
                if isinstance(params, dict) and "retry_after" in params:
                    retry_after = float(params["retry_after"])
            except Exception:
                retry_after = None

            return False, retry_after, f"{error_code}: {description}" if error_code or description else "telegram error"
        except Exception as e:
            return False, None, str(e)
    
    def _api_call(self, method: str, params: dict | None = None) -> dict | None:
        """Вызов Telegram API (без выбрасывания исключений наружу)."""
        url = self.API_URL.format(token=self.config.bot_token, method=method)

        try:
            if params:
                data = urllib.parse.urlencode(params).encode("utf-8")
                req = urllib.request.Request(url, data=data)
            else:
                req = urllib.request.Request(url)

            # таймаут чуть больше, чтобы не ронять отправку при кратком лаге сети
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Telegram обычно возвращает JSON даже при 4xx/5xx
            try:
                body = e.read().decode("utf-8", errors="replace")
                parsed = json.loads(body)
                return parsed
            except Exception:
                return {
                    "ok": False,
                    "error_code": getattr(e, "code", None),
                    "description": str(e),
                }
        except (urllib.error.URLError, TimeoutError) as e:
            logger.warning(f"Telegram API network error: {e}")
            return None
        except Exception as e:
            logger.error(f"Telegram API error: {e}")
            return None
