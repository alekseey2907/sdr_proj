"""
RF Event Analyzer - Main Monitor Engine
"""
from __future__ import annotations

import logging
import signal
import sys
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np

from rf_analyzer.core.config import AppConfig, FrequencyRange, RFEvent
from rf_analyzer.detection.detector import EventDetector
from rf_analyzer.rf.sdr_device import SDRDevice, create_device
from rf_analyzer.rf.signal_processor import SignalProcessor, SpectrumResult
from rf_analyzer.storage.event_storage import EventStorage

logger = logging.getLogger(__name__)


class MonitorState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class MonitorStats:
    """Статистика мониторинга"""
    state: MonitorState
    start_time: datetime | None
    total_samples: int
    total_spectrums: int
    events_detected: int
    current_range: str
    current_freq_mhz: float
    noise_floor_db: float
    uptime_seconds: float
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "total_samples": self.total_samples,
            "total_spectrums": self.total_spectrums,
            "events_detected": self.events_detected,
            "current_range": self.current_range,
            "current_freq_mhz": self.current_freq_mhz,
            "noise_floor_db": self.noise_floor_db,
            "uptime_seconds": self.uptime_seconds,
        }


class RFMonitor:
    """Главный движок мониторинга RF"""
    
    def __init__(
        self,
        config: AppConfig,
        storage: EventStorage,
        on_event: Callable[[RFEvent], None] | None = None,
        on_event_started: Callable[[RFEvent], None] | None = None,
        on_state_change: Callable[[MonitorState], None] | None = None
    ):
        self.config = config
        self.storage = storage
        self.on_event = on_event
        self.on_event_started = on_event_started
        self.on_state_change = on_state_change
        
        self._device: SDRDevice | None = None
        self._detector: EventDetector | None = None
        self._processor: SignalProcessor | None = None
        
        self._state = MonitorState.STOPPED
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # Не на паузе по умолчанию
        
        # Статистика
        self._start_time: datetime | None = None
        self._total_samples = 0
        self._total_spectrums = 0
        self._events_detected = 0
        self._current_range_idx = 0
        self._last_stats_log_time = 0.0  # Для периодического логирования статистики

        self._last_center_freq: float | None = None
        self._last_recover_time = 0.0

        self._last_start_error_message: str | None = None
        self._last_start_error_trace: str | None = None
        
        self._lock = threading.Lock()
    
    @property
    def state(self) -> MonitorState:
        return self._state
    
    def _set_state(self, state: MonitorState) -> None:
        self._state = state
        if self.on_state_change:
            self.on_state_change(state)
    
    def start(self) -> bool:
        """Запустить мониторинг"""
        if self._state in (MonitorState.RUNNING, MonitorState.STARTING):
            logger.warning("Monitor already running")
            return False
        
        if not self.config.ranges:
            logger.error("No frequency ranges configured")
            return False
        
        self._set_state(MonitorState.STARTING)
        
        try:
            self._last_start_error_message = None
            self._last_start_error_trace = None

            # Создаём устройство
            self._device = create_device(self.config.device)
            if not self._device.open():
                raise RuntimeError("Failed to open SDR device")
            
            # Настраиваем
            self._device.set_sample_rate(self.config.device.sample_rate)
            self._device.set_gain(self.config.device.gain)
            
            # Создаём детектор
            self._detector = EventDetector(
                config=self.config.detection,
                ranges=self.config.ranges,
                on_event_callback=self._on_event_detected,
                on_event_started_callback=self._on_event_started,
            )
            
            # Создаём процессор
            self._processor = SignalProcessor(self.config.detection)
            
            # Запускаем поток мониторинга
            self._stop_event.clear()
            self._pause_event.set()
            self._start_time = datetime.now()
            self._events_detected = 0
            self._total_samples = 0
            self._total_spectrums = 0
            self._last_activity_time = time.time()  # Для watchdog
            self._last_center_freq = None
            self._last_recover_time = 0.0
            
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True
            )
            self._monitor_thread.start()
            
            self._set_state(MonitorState.RUNNING)
            logger.info("Monitor started")
            return True
            
        except Exception as e:
            self._last_start_error_message = str(e)
            self._last_start_error_trace = traceback.format_exc()
            logger.error(f"Failed to start monitor: {e}", exc_info=True)
            self._cleanup()
            self._set_state(MonitorState.ERROR)
            return False

    @property
    def last_start_error_message(self) -> str | None:
        return self._last_start_error_message

    @property
    def last_start_error_trace(self) -> str | None:
        return self._last_start_error_trace
    
    def stop(self) -> None:
        """Остановить мониторинг"""
        if self._state == MonitorState.STOPPED:
            return
        
        self._set_state(MonitorState.STOPPING)
        self._stop_event.set()
        self._pause_event.set()  # Разблокировать если на паузе
        
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)
        
        # Завершаем незавершённые события
        if self._detector:
            events = self._detector.flush()
            for event in events:
                self.storage.save_event(event)
        
        self._cleanup()
        self._set_state(MonitorState.STOPPED)
        logger.info("Monitor stopped")
    
    def set_gain(self, gain: float) -> None:
        """Динамическое изменение усиления SDR устройства"""
        if self._device and self._state == MonitorState.RUNNING:
            self._device.set_gain(gain)
            self.config.device.gain = gain
            logger.info(f"Gain updated to {gain:.1f} dB")
    
    def set_threshold(self, threshold_db: float) -> None:
        """Динамическое изменение порога детекции"""
        if self._detector and self._state == MonitorState.RUNNING:
            self._detector.set_threshold(threshold_db)
            # Обновляем config для всех активных диапазонов
            for r in self.config.ranges:
                if r.enabled:
                    r.threshold_db = threshold_db
            logger.info(f"Threshold updated to {threshold_db:.1f} dB")
    
    def pause(self) -> None:
        """Поставить на паузу"""
        if self._state == MonitorState.RUNNING:
            self._pause_event.clear()
            self._set_state(MonitorState.PAUSED)
            logger.info("Monitor paused")
    
    def resume(self) -> None:
        """Продолжить после паузы"""
        if self._state == MonitorState.PAUSED:
            self._pause_event.set()
            self._set_state(MonitorState.RUNNING)
            logger.info("Monitor resumed")
    
    def _cleanup(self) -> None:
        """Очистка ресурсов"""
        if self._device:
            self._device.close()
            self._device = None
        self._detector = None
        self._processor = None
    
    def _monitor_loop(self) -> None:
        """Основной цикл мониторинга"""
        # Получаем активные диапазоны из конфига
        ranges = [r for r in self.config.ranges if r.enabled]
        if not ranges:
            logger.error("No enabled ranges")
            return
        
        # Уменьшаем количество сэмплов для RTL-SDR
        # ВАЖНО: Читать слишком маленькие блоки (например 2048) неэффективно для USB.
        # Лучше читать блок побольше (например 32к или 128к), а потом брать из него нужное.
        # Для FC0012 и USB 2.0 лучше использовать 16k-32k.
        min_samples = 32 * 1024 
        target_fft = self.config.detection.fft_size
        samples_per_read = max(min_samples, target_fft * 8)
        
        dwell_time = 3.0  # Меньше смен частоты -> стабильнее для FC0012
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        logger.info(f"Monitor loop started: {len(ranges)} ranges, samples_per_read={samples_per_read}")
        for r in ranges:
            logger.info(f"  Range: {r.name} = {r.start_freq/1e6:.3f} - {r.stop_freq/1e6:.3f} MHz (center: {r.center_freq/1e6:.3f} MHz)")
        
        while not self._stop_event.is_set():
            # Ждём если на паузе
            self._pause_event.wait()
            
            if self._stop_event.is_set():
                break
            
            # Проверяем доступность устройства
            # Для RTL-SDR проверяем _device._device, для LibreSDR - _ctx, для USRP - _soapy
            device_ok = False
            if self._device:
                # Сначала проверяем тип устройства
                device_class = self._device.__class__.__name__
                if device_class == 'SimulatedDevice':
                    device_ok = True  # Симулированное всегда доступно
                elif device_class == 'USRPDevice' and hasattr(self._device, '_soapy') and self._device._soapy is not None:
                    device_ok = True  # USRP via SoapySDR ctypes
                elif hasattr(self._device, '_device') and self._device._device is not None:
                    device_ok = True  # RTL-SDR
                elif hasattr(self._device, '_ctx') and self._device._ctx is not None:
                    device_ok = True  # LibreSDR
                elif hasattr(self._device, '_hackrf') and self._device._hackrf is not None:
                    device_ok = True  # HackRF
            
            if not device_ok:
                logger.error("Device disconnected, stopping monitor")
                self._set_state(MonitorState.ERROR)
                break
            
            # Текущий диапазон (с проверкой индекса)
            if self._current_range_idx >= len(ranges):
                self._current_range_idx = 0
            
            freq_range = ranges[self._current_range_idx]
            
            # Получаем sample_rate из конфигурации устройства
            sample_rate = self._device.config.sample_rate
            
            # --- Logic for sweeping wide ranges ---
            # ВАЖНО: FC0012 tuner НЕ ПОДДЕРЖИВАЕТ частотный хоппинг!
            # Но для RTL-SDR v4 (R828D) хоппинг работает нормально.
            # Включаем для всех, так как v4 сейчас стандарт.
            supports_hopping = True 
            
            center_freqs = []
            
            # Если устройство не поддерживает хоппинг ИЛИ диапазон узкий - используем центр
            if not supports_hopping or freq_range.bandwidth <= sample_rate:
                center_freqs.append(freq_range.center_freq)
                step_dwell = dwell_time
            else:
                # Для устройств с поддержкой хоппинга (USRP, HackRF, RTLSDR) - делаем sweep
                step_size = sample_rate * 0.8
                current_f = freq_range.start_freq + sample_rate / 2.0
                target_end = freq_range.stop_freq - sample_rate / 2.0
                
                while current_f < target_end + 10.0:
                    center_freqs.append(current_f)
                    current_f += step_size
                
                last_step_center = freq_range.stop_freq - sample_rate / 2.0
                if not center_freqs or (last_step_center > center_freqs[-1]):
                     center_freqs.append(last_step_center)
                
                # Ускоренный режим сканирования (0.1с на шаг вместо 0.5с)
                step_dwell = 0.1
            
            # Iterate over all frequency steps for this range
            for center_freq in center_freqs:
                if self._stop_event.is_set():
                    break

                # Pause check inside the loop
                if self._pause_event.is_set() == False:
                    self._pause_event.wait()

                try:
                    # Пропускаем сканирование если частота заведомо некорректная
                    # (чтобы не убивать нестабильные тюнеры вроде FC0012)
                    if hasattr(self._device, 'get_capabilities'):
                        caps = self._device.get_capabilities()
                        if center_freq < caps.min_freq or center_freq > caps.max_freq:
                            # Логируем только один раз для диапазона
                            if center_freq == center_freqs[0]: 
                                logger.warning(f"Range {freq_range.name} ({center_freq/1e6:.1f} MHz) out of device capabilities ({caps.min_freq/1e6:.1f}-{caps.max_freq/1e6:.1f} MHz). Skipping.")
                            continue

                    # Настраиваем частоту
                    # Не перенастраиваем, если частота не менялась
                    if self._last_center_freq is None or abs(center_freq - self._last_center_freq) >= 1.0:
                        logger.info(f"Setting center frequency to {center_freq/1e6:.3f} MHz")
                        if not self._device.set_center_freq(center_freq):
                            consecutive_errors += 1

                            # Вместо немедленной остановки пробуем восстановиться с backoff
                            if consecutive_errors >= 3:
                                now = time.time()
                                if now - self._last_recover_time >= 10.0:
                                    self._last_recover_time = now
                                    logger.error(
                                        "Too many frequency set errors, attempting device reopen..."
                                    )
                                    try:
                                        self._device.close()
                                        time.sleep(2.0)
                                        if not self._device.open():
                                            raise RuntimeError("Failed to reopen device")
                                        # Восстанавливаем настройки устройства после reopen
                                        self._device.set_sample_rate(self.config.device.sample_rate)
                                        self._device.set_gain(self.config.device.gain)
                                        time.sleep(1.0)
                                        # Переустанавливаем частоту один раз
                                        if not self._device.set_center_freq(center_freq):
                                            raise RuntimeError("Failed to set frequency after reopen")
                                        consecutive_errors = 0
                                        self._last_center_freq = center_freq
                                    except Exception as re:
                                        logger.error(f"Device reopen failed: {re}")
                                        if consecutive_errors >= max_consecutive_errors:
                                            logger.error("Too many frequency set errors, stopping")
                                            self._set_state(MonitorState.ERROR)
                                            break
                                time.sleep(0.2)
                                continue

                            if consecutive_errors >= max_consecutive_errors:
                                logger.error("Too many frequency set errors, stopping")
                                self._set_state(MonitorState.ERROR)
                                break
                            time.sleep(0.2)
                            continue
                        
                        # Added stabilization delay for fragile tuners (FC0012)
                        time.sleep(0.05)
                        
                        self._last_center_freq = center_freq
                        consecutive_errors = 0  # Сброс при успехе
                    
                    # Сканируем диапазон некоторое время (step_dwell)
                    scan_start = time.time()
                    
                    while time.time() - scan_start < step_dwell:
                        if self._stop_event.is_set():
                            break
                        
                        # Проверяем устройство (используем ту же логику что и в начале цикла)
                        device_ok = False
                        if self._device:
                            device_class = self._device.__class__.__name__
                            if device_class == 'SimulatedDevice':
                                device_ok = True
                            elif device_class == 'USRPDevice' and hasattr(self._device, '_soapy') and self._device._soapy is not None:
                                device_ok = True
                            elif hasattr(self._device, '_device') and self._device._device is not None:
                                device_ok = True  # RTL-SDR
                            elif hasattr(self._device, '_ctx') and self._device._ctx is not None:
                                device_ok = True  # LibreSDR
                            elif hasattr(self._device, '_hackrf') and self._device._hackrf is not None:
                                device_ok = True  # HackRF
                        
                        if not device_ok:
                            logger.error("Device lost during scan")
                            break
                        
                        # Читаем сэмплы
                        samples = self._device.read_samples(samples_per_read)
                        logger.debug(f"Read {len(samples)} samples")
                        if len(samples) == 0:
                            consecutive_errors += 1
                            if consecutive_errors >= max_consecutive_errors:
                                logger.error("Too many read errors")
                                break
                            time.sleep(0.01)
                            continue
                        
                        consecutive_errors = 0
                        self._total_samples += len(samples)
                        
                        # Обрабатываем
                        timestamp = time.time()
                        spectrum = self._processor.compute_spectrum(
                            samples, center_freq,
                            self.config.device.sample_rate,
                            timestamp
                        )
                        self._total_spectrums += 1
                        if self._total_spectrums % 10 == 0:
                            logger.info(f"Processed {self._total_spectrums} spectrums, avg power: {spectrum.avg_power:.1f} dB")
                        # Превентивные reset'ы отключены: на FC0012 частые close/open часто
                        # приводят к rtlsdr_demod_write_reg failed (-9). Восстановление делаем
                        # только при реальных ошибках (см. выше).
                        
                        # Очистка памяти каждые 1000 спектров (для 24+ часов работы)
                        if self._total_spectrums % 1000 == 0:
                            logger.info(f"Memory cleanup at {self._total_spectrums} spectrums")
                            import gc
                            collected = gc.collect()
                            logger.debug(f"Garbage collector freed {collected} objects")
                        
                        # Логирование статистики каждый час
                        current_time = time.time()
                        if current_time - self._last_stats_log_time > 3600:  # 1 час
                            self._last_stats_log_time = current_time
                            uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0
                            logger.info(
                                f"Hourly stats: uptime={uptime/3600:.1f}h, "
                                f"spectrums={self._total_spectrums}, "
                                f"events={self._events_detected}, "
                                f"samples={self._total_samples}"
                            )
                        
                        # Детекция событий
                        self._detector.process_spectrum(spectrum)
                    
                except Exception as e:
                    logger.error(f"Monitor loop error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many errors in monitor loop, stopping")
                        self._set_state(MonitorState.ERROR)
                        break
                    time.sleep(0.1)
            
            # Конец цикла по frequency steps
            # Переходим к следующему диапазону
            self._current_range_idx = (self._current_range_idx + 1) % len(ranges)
                
            # except Exception as e: <--- REMOVED (moved up)
    
    def _on_event_detected(self, event: RFEvent) -> None:
        """Обработчик обнаруженного события"""
        with self._lock:
            self._events_detected += 1
        
        # Сохраняем в БД
        event.id = self.storage.save_event(event)
        
        # Вызываем callback
        if self.on_event:
            self.on_event(event)
        
        logger.info(f"Event detected: {event.range_name}, {event.event_type.value}")

    def _on_event_started(self, event: RFEvent) -> None:
        """Событие стало значимым (достигло min_duration) и ещё активно."""
        # Важно: активное событие ещё не завершено, поэтому в БД его НЕ сохраняем.
        if self.on_event_started:
            self.on_event_started(event)
    
    def get_stats(self) -> MonitorStats:
        """Получить статистику мониторинга"""
        # Обновляем время активности для watchdog
        self._last_activity_time = time.time()
        
        ranges = [r for r in self.config.ranges if r.enabled]
        current_range = ""
        current_freq = 0.0
        noise_floor = -100.0
        
        if ranges and self._current_range_idx < len(ranges):
            freq_range = ranges[self._current_range_idx]
            current_range = freq_range.name
            current_freq = freq_range.center_freq / 1e6
        
        if self._processor:
            noise_floor = self._processor.noise_floor.avg_level
        
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
        
        active_events = 0
        if self._detector:
            try:
                active_events = int(self._detector.get_stats().get("active_events", 0))
            except Exception:
                active_events = 0

        return MonitorStats(
            state=self._state,
            start_time=self._start_time,
            total_samples=self._total_samples,
            total_spectrums=self._total_spectrums,
            # self._events_detected — завершённые события (сохранены в БД). Для UI полезнее
            # показывать ещё и активные события, чтобы счётчик не был 0 при continuous-сигнале.
            events_detected=self._events_detected + active_events,
            current_range=current_range,
            current_freq_mhz=current_freq,
            noise_floor_db=noise_floor,
            uptime_seconds=uptime,
        )
    
    def update_config(self, config: AppConfig) -> None:
        """Обновить конфигурацию на лету"""
        self.config = config
        
        if self._detector:
            self._detector.update_ranges(config.ranges)
        
        if self._device and self._state == MonitorState.RUNNING:
            self._device.set_gain(config.device.gain)


def run_monitor_daemon(
    config_path: Path,
    on_event: Callable[[RFEvent], None] | None = None
) -> None:
    """Запуск монитора как демона"""
    
    # Загружаем конфиг
    config = AppConfig.load(config_path)
    
    # Создаём хранилище
    storage = EventStorage(config.output.database_path)
    
    # Создаём монитор
    monitor = RFMonitor(config, storage, on_event=on_event)
    
    # Обработка сигналов
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        monitor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем
    if not monitor.start():
        logger.error("Failed to start monitor")
        sys.exit(1)
    
    logger.info("Monitor daemon running. Press Ctrl+C to stop.")
    
    # Ждём
    while monitor.state == MonitorState.RUNNING:
        time.sleep(1)
