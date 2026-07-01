"""
RF Event Analyzer - Event Detection Engine
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

from rf_analyzer.core.config import EventType, FrequencyRange, RFEvent
from rf_analyzer.rf.signal_processor import (
    PeriodicityAnalyzer,
    SignalProcessor,
    SpectrumResult,
)

if TYPE_CHECKING:
    from rf_analyzer.core.config import DetectionConfig

logger = logging.getLogger(__name__)


@dataclass
class ActiveEvent:
    """Активное (незавершённое) событие"""
    event: RFEvent
    last_update: float
    power_samples: list[float] = field(default_factory=list)
    
    def update(self, power_db: float, timestamp: float) -> None:
        self.power_samples.append(power_db)
        self.last_update = timestamp
        self.event.max_power_db = max(self.event.max_power_db, power_db)
        self.event.avg_power_db = float(np.mean(self.power_samples))


class EventDetector:
    """Движок детекции RF-событий"""
    
    def __init__(
        self, 
        config: DetectionConfig,
        ranges: list[FrequencyRange],
        on_event_callback: Callable[[RFEvent], None] | None = None,
        on_event_started_callback: Callable[[RFEvent], None] | None = None,
    ):
        self.config = config
        self.ranges = {r.name: r for r in ranges if r.enabled}
        self.on_event = on_event_callback
        self.on_event_started = on_event_started_callback
        
        self._processor = SignalProcessor(config)
        self._periodicity_analyzers: dict[str, PeriodicityAnalyzer] = {
            name: PeriodicityAnalyzer() for name in self.ranges
        }
        
        self._active_events: dict[str, ActiveEvent] = {}
        self._lock = threading.Lock()
        self._spectrum_count = 0
        self._last_periodic_check = 0.0
        
        # Отслеживание "виртуального" дрона (склейка событий между диапазонами)
        self._last_wideband_detection: float | None = None  # Время последнего обнаружения широкополосного сигнала
        self._wideband_timeout = 5.0  # Если за 5 секунд не увидели в другом диапазоне - считаем что дрон ушёл
    
    def process_spectrum(self, spectrum: SpectrumResult) -> list[RFEvent]:
        """
        Обработать спектр и вернуть завершённые события
        """
        completed_events: list[RFEvent] = []
        started_events: list[RFEvent] = []
        current_time = spectrum.timestamp
        
        with self._lock:
            self._spectrum_count += 1
            
            # Обновляем шумовой фон
            if self._spectrum_count <= self.config.noise_floor_averaging:
                self._processor.update_noise_floor(spectrum)
            elif self._spectrum_count % 10 == 0:
                # Периодическое обновление
                self._processor.update_noise_floor(spectrum)
            
            # Проверяем каждый диапазон
            for freq_range in self.ranges.values():
                completed, started = self._check_range(spectrum, freq_range, current_time)
                completed_events.extend(completed)
                if started:
                    started_events.append(started)
            
            # Периодическая проверка на периодичность
            if current_time - self._last_periodic_check > self.config.periodic_check_interval:
                self._check_periodicity(current_time)
                self._last_periodic_check = current_time
            
            # Закрываем устаревшие события
            timeout_events = self._close_stale_events(current_time)
            completed_events.extend(timeout_events)
        
        # Callback для "старта" (когда событие стало значимым по min_duration)
        for event in started_events:
            if self.on_event_started:
                self.on_event_started(event)

        # Callback для завершённых событий
        for event in completed_events:
            if self.on_event:
                self.on_event(event)
        
        return completed_events
    
    def _check_range(
        self, 
        spectrum: SpectrumResult, 
        freq_range: FrequencyRange,
        current_time: float
    ) -> tuple[list[RFEvent], RFEvent | None]:
        """Проверка одного диапазона на события"""
        completed_events: list[RFEvent] = []
        started_event: RFEvent | None = None
        range_name = freq_range.name
        
        # Получаем мощность в диапазоне
        detected, max_power, avg_power, peak_freq = self._processor.detect_threshold_exceeded(
            spectrum,
            freq_range.threshold_db,
            freq_range.start_freq,
            freq_range.stop_freq
        )
        
        # Обновляем анализатор периодичности
        self._periodicity_analyzers[range_name].add_sample(current_time, max_power)
        
        if detected:
            # Проверяем тип события
            event_type = self._classify_event(
                spectrum, freq_range, max_power, avg_power
            )
            
            if range_name in self._active_events:
                # Обновляем существующее событие
                active = self._active_events[range_name]
                active.update(max_power, current_time)

                # Событие стало "достаточно длинным" (или всё ещё активно):
                # отдаём наружу, а анти-спам делаем на уровне TelegramNotifier (cooldown).
                duration_ms = (current_time - active.event.start_time.timestamp()) * 1000
                if duration_ms >= freq_range.min_duration_ms:
                    started_event = active.event
            elif self._last_wideband_detection is not None and \
                 (current_time - self._last_wideband_detection) < self._wideband_timeout and \
                 event_type == EventType.WIDEBAND:
                # "Склейка": Если недавно (<5 сек) видели широкополосный сигнал в ДРУГОМ диапазоне,
                # считаем что это тот же дрон переключился. Продлеваем виртуальное событие.
                logger.info(f"Wideband signal continuity: {range_name} (drone likely switched bands)")
                # Создаём событие, но помечаем как "продолжение"
                event = RFEvent(
                    start_time=datetime.fromtimestamp(self._last_wideband_detection),  # Время первого обнаружения
                    range_name=range_name,
                    center_freq=peak_freq,
                    bandwidth=freq_range.bandwidth,
                    max_power_db=max_power,
                    avg_power_db=avg_power,
                    event_type=event_type,
                )
                self._active_events[range_name] = ActiveEvent(
                    event=event,
                    last_update=current_time,
                    power_samples=[max_power],
                )
                started_event = event  # Сразу уведомляем (это уже не "новый" дрон)
            else:
                # Создаём новое событие
                event = RFEvent(
                    start_time=datetime.fromtimestamp(current_time),
                    range_name=range_name,
                    center_freq=peak_freq,
                    bandwidth=freq_range.bandwidth,
                    max_power_db=max_power,
                    avg_power_db=avg_power,
                    event_type=event_type,
                )
                self._active_events[range_name] = ActiveEvent(
                    event=event,
                    last_update=current_time,
                    power_samples=[max_power],
                )
                logger.debug(f"Event started: {range_name} at {peak_freq/1e6:.3f} MHz")
        else:
            # Порог не превышен - закрываем активное событие если есть
            if range_name in self._active_events:
                completed = self._close_event(range_name, current_time)
                if completed:
                    completed_events.append(completed)

        return completed_events, started_event
    
    def _classify_event(
        self,
        spectrum: SpectrumResult,
        freq_range: FrequencyRange,
        max_power: float,
        avg_power: float
    ) -> EventType:
        """Классификация типа события"""
        
        # Измеряем ширину сигнала
        signal_width_hz = self._processor.detect_signal_width(
            spectrum,
            freq_range.threshold_db,
            freq_range.start_freq,
            freq_range.stop_freq
        )
        
        # Проверяем на широкополосный сигнал (характерно для дронов с FHSS)
        # Дроны: ELRS/Crossfire обычно занимают 500 кГц - 10 МГц
        # Брелки/Рации: обычно < 50 кГц
        DRONE_MIN_WIDTH_HZ = 200_000  # 200 кГц минимум для подозрения на дрон
        
        if signal_width_hz > DRONE_MIN_WIDTH_HZ:
            logger.info(f"Wide-band signal detected: {signal_width_hz/1e6:.2f} MHz (potential drone/FHSS)")
            # Обновляем время последнего обнаружения
            self._last_wideband_detection = spectrum.timestamp
            # Это похоже на дрон - возвращаем специальный тип
            return EventType.WIDEBAND
        
        # Проверяем импульс
        is_impulse, excess = self._processor.detect_impulse(
            spectrum,
            self.config.impulse_threshold_db,
            freq_range.start_freq,
            freq_range.stop_freq
        )
        if is_impulse:
            return EventType.IMPULSE
        
        # Проверяем сдвиг шума
        is_shift, shift_db = self._processor.detect_noise_floor_shift(spectrum)
        if is_shift:
            return EventType.NOISE_FLOOR_SHIFT
        
        # Проверяем периодичность
        is_periodic, period = self._periodicity_analyzers[freq_range.name].detect_periodicity()
        if is_periodic:
            return EventType.PERIODIC_ACTIVITY
        
        # Если разница между max и avg маленькая - непрерывное излучение
        if max_power - avg_power < 3.0:
            return EventType.CONTINUOUS
        
        # По умолчанию - превышение порога
        return EventType.THRESHOLD_EXCEEDED
    
    def _close_event(self, range_name: str, current_time: float) -> RFEvent | None:
        """Закрыть активное событие"""
        if range_name not in self._active_events:
            return None
        
        active = self._active_events.pop(range_name)
        event = active.event
        
        event.end_time = datetime.fromtimestamp(current_time)
        event.duration_ms = (current_time - event.start_time.timestamp()) * 1000
        
        # Фильтр по минимальной длительности
        freq_range = self.ranges.get(range_name)
        if freq_range and event.duration_ms < freq_range.min_duration_ms:
            logger.debug(f"Event too short, discarded: {event.duration_ms:.0f}ms")
            return None
        
        # Генерируем комментарий
        event.comment = event.generate_comment()
        
        logger.info(f"Event completed: {range_name}, duration: {event.duration_ms:.0f}ms")
        return event
    
    def _close_stale_events(self, current_time: float) -> list[RFEvent]:
        """Закрыть устаревшие события (без обновлений)"""
        completed = []
        timeout_ms = self.config.min_event_gap_ms / 1000.0
        
        stale_ranges = [
            name for name, active in self._active_events.items()
            if current_time - active.last_update > timeout_ms
        ]
        
        for range_name in stale_ranges:
            event = self._close_event(range_name, current_time)
            if event:
                completed.append(event)
        
        return completed
    
    def _check_periodicity(self, current_time: float) -> None:
        """Проверка периодической активности во всех диапазонах"""
        for range_name, analyzer in self._periodicity_analyzers.items():
            is_periodic, period = analyzer.detect_periodicity()
            if is_periodic:
                logger.debug(f"Periodic activity in {range_name}: period={period:.2f}s")
    
    def flush(self) -> list[RFEvent]:
        """Завершить все активные события"""
        completed = []
        current_time = time.time()
        
        with self._lock:
            for range_name in list(self._active_events.keys()):
                event = self._close_event(range_name, current_time)
                if event:
                    completed.append(event)
                    if self.on_event:
                        self.on_event(event)
        
        return completed
    
    def update_ranges(self, ranges: list[FrequencyRange]) -> None:
        """Обновить конфигурацию диапазонов"""
        with self._lock:
            # Закрываем события для удалённых диапазонов
            new_names = {r.name for r in ranges if r.enabled}
            for name in list(self._active_events.keys()):
                if name not in new_names:
                    self._close_event(name, time.time())
            
            self.ranges = {r.name: r for r in ranges if r.enabled}
            
            # Создаём новые анализаторы периодичности
            for name in new_names:
                if name not in self._periodicity_analyzers:
                    self._periodicity_analyzers[name] = PeriodicityAnalyzer()
    
    def set_threshold(self, threshold_db: float) -> None:
        """Динамическое обновление порога для всех диапазонов"""
        with self._lock:
            for r in self.ranges.values():
                r.threshold_db = threshold_db
            logger.debug(f"Threshold updated to {threshold_db:.1f} dB for all ranges")
    
    def get_stats(self) -> dict:
        """Получить статистику детектора"""
        return {
            "spectrum_count": self._spectrum_count,
            "active_events": len(self._active_events),
            "noise_floor_db": self._processor.noise_floor.avg_level,
            "monitored_ranges": len(self.ranges),
        }
    
    def set_threshold(self, threshold_db: float) -> None:
        """Dynamically update threshold for all ranges"""
        with self._lock:
            for r in self.ranges.values():
                r.threshold_db = threshold_db
