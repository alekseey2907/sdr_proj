"""
RF Event Analyzer - SDR Device Abstraction Layer
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from rf_analyzer.core.config import DeviceConfig

logger = logging.getLogger(__name__)


def _setup_dll_paths():
    """Настройка путей к DLL библиотекам для Windows"""
    if sys.platform != 'win32':
        return
    
    # Находим корневую папку проекта
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent  # rf/analyzer/src -> project root
    
    # Папка с DLL
    libs_dir = project_root / "libs"
    
    if libs_dir.exists():
        libs_path = str(libs_dir)
        
        # Добавляем в PATH
        if libs_path not in os.environ.get('PATH', ''):
            os.environ['PATH'] = libs_path + os.pathsep + os.environ.get('PATH', '')
            logger.debug(f"Added to PATH: {libs_path}")
        
        # Для Python 3.8+ используем add_dll_directory
        if hasattr(os, 'add_dll_directory'):
            try:
                os.add_dll_directory(libs_path)
                logger.debug(f"Added DLL directory: {libs_path}")
            except Exception as e:
                logger.warning(f"Failed to add DLL directory: {e}")
        
        # Проверяем наличие rtlsdr.dll
        rtlsdr_dll = libs_dir / "rtlsdr.dll"
        if rtlsdr_dll.exists():
            logger.info(f"Found rtlsdr.dll: {rtlsdr_dll}")
        else:
            logger.warning(f"rtlsdr.dll not found in {libs_dir}")
    else:
        logger.warning(f"Libs directory not found: {libs_dir}")


# Настраиваем пути к DLL при импорте модуля
_setup_dll_paths()


@dataclass
class SDRCapabilities:
    """Характеристики SDR устройства"""
    min_freq: float
    max_freq: float
    min_sample_rate: float
    max_sample_rate: float
    min_gain: float
    max_gain: float
    name: str


class SDRDevice(ABC):
    """Абстрактный базовый класс для SDR устройств"""
    
    def __init__(self, config: DeviceConfig):
        self.config = config
        self._is_streaming = False
        self._stream_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._sample_callback: Callable[[NDArray[np.complex64]], None] | None = None
    
    @abstractmethod
    def open(self) -> bool:
        """Открыть соединение с устройством"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Закрыть соединение"""
        pass
    
    @abstractmethod
    def set_center_freq(self, freq: float) -> bool:
        """Установить центральную частоту"""
        pass
    
    @abstractmethod
    def set_sample_rate(self, rate: float) -> bool:
        """Установить частоту дискретизации"""
        pass
    
    @abstractmethod
    def set_gain(self, gain: float) -> bool:
        """Установить усиление"""
        pass
    
    @abstractmethod
    def read_samples(self, num_samples: int) -> NDArray[np.complex64]:
        """Прочитать заданное количество сэмплов"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> SDRCapabilities:
        """Получить характеристики устройства"""
        pass
    
    @property
    def is_streaming(self) -> bool:
        return self._is_streaming
    
    def start_streaming(self, callback: Callable[[NDArray[np.complex64]], None], 
                       samples_per_read: int = 262144) -> bool:
        """Запустить потоковое чтение"""
        if self._is_streaming:
            return False
        
        self._sample_callback = callback
        self._stop_event.clear()
        self._is_streaming = True
        
        self._stream_thread = threading.Thread(
            target=self._streaming_loop,
            args=(samples_per_read,),
            daemon=True
        )
        self._stream_thread.start()
        return True
    
    def stop_streaming(self) -> None:
        """Остановить потоковое чтение"""
        if not self._is_streaming:
            return
        
        self._stop_event.set()
        if self._stream_thread:
            self._stream_thread.join(timeout=2.0)
        self._is_streaming = False
        self._sample_callback = None
    
    def _streaming_loop(self, samples_per_read: int) -> None:
        """Внутренний цикл потокового чтения"""
        while not self._stop_event.is_set():
            try:
                samples = self.read_samples(samples_per_read)
                if self._sample_callback and len(samples) > 0:
                    self._sample_callback(samples)
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                time.sleep(0.1)


class RTLSDRDevice(SDRDevice):
    """Реализация для RTL-SDR устройств"""
    
    # Диапазоны частот для разных тюнеров RTL-SDR
    TUNER_FREQ_RANGES = {
        'E4000': (52e6, 2200e6),      # 52 MHz - 2.2 GHz (с дырой 1100-1250 MHz)
        'FC0012': (22e6, 948.6e6),    # 22 MHz - 948.6 MHz  
        'FC0013': (22e6, 1100e6),     # 22 MHz - 1.1 GHz
        'FC2580': (146e6, 308e6),     # Два диапазона: 146-308 MHz и 438-924 MHz
        'R820T': (24e6, 1766e6),      # 24 MHz - 1.766 GHz
        'R828D': (24e6, 1766e6),      # 24 MHz - 1.766 GHz
        'UNKNOWN': (24e6, 1700e6),    # Консервативный диапазон по умолчанию
    }
    
    # Нестабильные зоны частот для разных тюнеров (лучше избегать)
    TUNER_UNSTABLE_RANGES = {
        'FC0012': [(580e6, 800e6)],   # Нестабильная зона 580-800 МГц для FC0012
        'E4000': [(1100e6, 1250e6)],  # Дыра в E4000
    }

    # pyrtlsdr/rtlsdr возвращает числовые коды тюнера (rtlsdr_tuner)
    # 0=UNKNOWN, 1=E4000, 2=FC0012, 3=FC0013, 4=FC2580, 5=R820T, 6=R828D
    TUNER_TYPE_CODE_MAP = {
        0: 'UNKNOWN',
        1: 'E4000',
        2: 'FC0012',
        3: 'FC0013',
        4: 'FC2580',
        5: 'R820T',
        6: 'R828D',
    }

    @classmethod
    def _normalize_tuner_type(cls, tuner: object) -> str:
        if tuner is None:
            return 'UNKNOWN'
        if isinstance(tuner, (int, np.integer)):
            return cls.TUNER_TYPE_CODE_MAP.get(int(tuner), 'UNKNOWN')
        return str(tuner)
    
    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._device = None
        self._error_count = 0
        self._max_errors = 5  # После этого числа ошибок останавливаем устройство
        self._read_delay = 0.01  # Задержка между чтениями (10ms)
        self._tuner_type = 'UNKNOWN'
        self._freq_min = 24e6
        self._freq_max = 1700e6
        self._recovery_attempts = 0
        self._max_recovery_attempts = 3  # Максимум попыток восстановления
        self._last_error_time = 0.0  # Время последней ошибки
        self._last_open_time = 0.0   # Время последнего открытия устройства
        self._min_reopen_interval = 5.0  # Минимум секунд между переоткрытиями
        self._successful_reads = 0  # Счётчик успешных чтений
        self._needs_recovery = False  # Флаг необходимости восстановления
        self._current_freq = 0.0  # Текущая частота для восстановления
        self._current_sample_rate = 0.0
        self._current_gain = 0.0
    
    def open(self) -> bool:
        """Открыть соединение с RTL-SDR"""
        try:
            _setup_dll_paths()
            from rtlsdr import RtlSdr
            
            logger.info(f"Opening RTL-SDR device index={self.config.device_index}")
            self._device = RtlSdr(device_index=self.config.device_index)
            self._last_open_time = time.time()
            
            # Увеличенная пауза для FC0012
            time.sleep(1.0)

            # Определяем тип тюнера как можно раньше.
            # Для FC0012 выставление sample_rate > 2.0 MSPS часто приводит к access violation.
            raw_tuner = self._device.get_tuner_type()
            self._tuner_type = self._normalize_tuner_type(raw_tuner)
            logger.info(f"Detected tuner: raw={raw_tuner!r}, name={self._tuner_type}")
            if self._tuner_type in self.TUNER_FREQ_RANGES:
                self._freq_min, self._freq_max = self.TUNER_FREQ_RANGES[self._tuner_type]
            else:
                self._freq_min, self._freq_max = self.TUNER_FREQ_RANGES['UNKNOWN']
            
            # Sample rate (с fallback на более безопасные значения)
            requested_rate = float(self.config.sample_rate)
            if self._tuner_type == 'FC0012' and requested_rate > 2.0e6:
                requested_rate = 2.0e6

            candidate_rates = [requested_rate, 2.0e6, 1.0e6]
            used_rate: float | None = None
            last_rate_error: Exception | None = None
            for rate in candidate_rates:
                if used_rate is not None and abs(rate - used_rate) < 1:
                    continue
                try:
                    self._device.sample_rate = rate
                    used_rate = rate
                    time.sleep(0.3)
                    break
                except Exception as e:
                    last_rate_error = e
                    logger.warning(f"Failed to set sample_rate={rate}: {e}")
                    time.sleep(0.5)
            if used_rate is None:
                raise RuntimeError(f"Failed to set sample rate (last error: {last_rate_error})")

            self._current_sample_rate = used_rate

            # Важно: синхронизируем конфиг с фактической частотой дискретизации.
            # Иначе Monitor.start() снова вызовет set_sample_rate() со старым значением
            # и может "убить" FC0012 (LIBUSB IO / access violation).
            if abs(used_rate - requested_rate) >= 1:
                self.config.sample_rate = used_rate

            # ВАЖНО: не трогаем center_freq/gain/read_samples здесь.
            # На нестабильных FC0012/USB это часто вызывает rtlsdr_demod_write_reg -9
            # и даже OSError access violation. Конфигурация выполняется позже
            # (и там уже есть троттлинг/восстановление).

            # Тюнер уже определён выше; оставляем значения как есть.
            
            logger.info(f"RTL-SDR opened: {self._tuner_type}, "
                       f"range {self._freq_min/1e6:.1f}-{self._freq_max/1e6:.1f} MHz")

            if used_rate != requested_rate:
                logger.warning(
                    f"Using fallback sample rate {used_rate:.0f} (requested {requested_rate:.0f})"
                )
            
            # Disable AGC modes by default to prevent unpredictable gain changes
            try:
                self._device.set_manual_gain_enabled(1)  # Enable manual gain
                self._device.set_agc_mode(0)             # Disable RTL AGC
            except Exception as e:
                logger.warning(f"Failed to set initial AGC/Gain parameters: {e}")
            
            # Сброс счётчиков
            self._error_count = 0
            self._recovery_attempts = 0
            self._needs_recovery = False
            self._successful_reads = 0
            
            return True
            
        except ImportError as e:
            logger.error(f"RTL-SDR library not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to open RTL-SDR: {e}")
            if self._device:
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None
            return False
    
    def close(self) -> None:
        self.stop_streaming()
        if self._device:
            try:
                self._device.close()
            except Exception as e:
                logger.error(f"Error closing RTL-SDR: {e}")
            self._device = None
    
    def set_center_freq(self, freq: float) -> bool:
        if not self._device:
            return False

        # Не дёргаем железо, если частота не меняется (FC0012 очень чувствителен
        # к частым операциям записи регистров и может падать с access violation).
        if self._current_freq and abs(freq - self._current_freq) < 1.0:
            return True
        
        # Проверка допустимого диапазона частот для данного тюнера
        if freq < self._freq_min or freq > self._freq_max:
            logger.error(f"Frequency {freq/1e6:.1f} MHz is out of range for {self._tuner_type} tuner "
                        f"({self._freq_min/1e6:.1f} - {self._freq_max/1e6:.1f} MHz)")
            return False
        
        # Проверка нестабильных зон
        if self._is_unstable_frequency(freq):
            logger.warning(f"Frequency {freq/1e6:.1f} MHz is in unstable range for {self._tuner_type} tuner - skipping")
            return False
        
        # Защита от слишком частых попыток при ошибках
        current_time = time.time()
        if self._error_count >= 3 and current_time - self._last_error_time < 2.0:
            logger.warning(f"Throttling freq changes due to errors (count={self._error_count})")
            # Попытка восстановления устройства (но не бесконечно)
            if self._error_count == 3 and self._recovery_attempts < self._max_recovery_attempts:
                logger.info(f"Attempting device recovery (attempt {self._recovery_attempts + 1}/{self._max_recovery_attempts})...")
                if self._attempt_recovery():
                    self._recovery_attempts += 1
                else:
                    self._recovery_attempts = self._max_recovery_attempts  # Больше не пытаемся
            return False
        
        try:
            # Дополнительная задержка перед сменой частоты для FC0012
            time.sleep(0.2)
            self._device.center_freq = freq
            self._current_freq = freq  # Сохраняем для восстановления
            # После смены частоты нужна задержка для стабилизации PLL
            time.sleep(0.25)  # Увеличена задержка для FC0012
            # Сбрасываем буфер после смены частоты
            try:
                _ = self._device.read_samples(4096)
            except Exception:
                pass
            self._error_count = 0  # Сброс счётчика при успехе
            self._last_error_time = 0
            self._recovery_attempts = 0  # Сброс счётчика восстановлений при успехе
            return True
        except Exception as e:
            logger.error(f"Failed to set frequency: {e}")
            self._error_count += 1
            self._last_error_time = current_time
            if self._error_count >= self._max_errors and self._recovery_attempts < self._max_recovery_attempts:
                logger.error("Too many errors, attempting recovery")
                self._attempt_recovery()
                self._recovery_attempts += 1
            return False
    
    def _is_unstable_frequency(self, freq: float) -> bool:
        """Проверить, находится ли частота в нестабильной зоне для данного тюнера"""
        unstable_ranges = self.TUNER_UNSTABLE_RANGES.get(self._tuner_type, [])
        for low, high in unstable_ranges:
            if low <= freq <= high:
                return True
        return False
    
    def _attempt_recovery(self) -> bool:
        """Попытка восстановить устройство после ошибок"""
        current_time = time.time()
        
        # Защита от слишком частого переоткрытия
        time_since_last_open = current_time - self._last_open_time
        if time_since_last_open < self._min_reopen_interval:
            wait_time = self._min_reopen_interval - time_since_last_open
            logger.warning(f"Throttling device reopen, waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
        
        logger.info("Attempting RTL-SDR recovery...")
        try:
            # Закрываем устройство
            if self._device:
                try:
                    self._device.close()
                except Exception:
                    pass
                self._device = None
            
            # Ждём дольше для USB reset
            time.sleep(2.0)
            
            # Пытаемся переоткрыть
            _setup_dll_paths()
            from rtlsdr import RtlSdr
            self._device = RtlSdr(device_index=self.config.device_index)
            self._last_open_time = time.time()
            time.sleep(0.5)
            
            self._device.sample_rate = self.config.sample_rate
            time.sleep(0.2)
            
            # Disable AGC/Enable manual gain during recovery too
            try:
                self._device.set_manual_gain_enabled(1)
                self._device.set_agc_mode(0)
                self._device.gain = self.config.gain  # Use configured gain instead of auto
            except Exception:
                pass
                
            time.sleep(0.2)
            
            # Тестовое чтение
            _ = self._device.read_samples(1024)
            time.sleep(0.1)
            
            self._error_count = 0
            logger.info("RTL-SDR recovery successful")
            return True
        except Exception as e:
            logger.error(f"RTL-SDR recovery failed: {e}")
            self._device = None
            return False
    
    def get_freq_range(self) -> tuple[float, float]:
        """Получить допустимый диапазон частот для тюнера"""
        return (self._freq_min, self._freq_max)
    
    def _handle_device_error(self):
        """Обработка критической ошибки устройства"""
        logger.warning("Handling device error - closing device")
        try:
            if self._device:
                self._device.close()
        except Exception:
            pass
        self._device = None
    
    def set_sample_rate(self, rate: float) -> bool:
        if not self._device:
            return False
            
        # Avoid redundant writes
        if self._current_sample_rate and abs(rate - self._current_sample_rate) < 1.0:
            return True

        requested_rate = float(rate)
        if self._tuner_type == 'FC0012' and requested_rate > 2.0e6:
            requested_rate = 2.0e6

        candidate_rates = [requested_rate, 2.0e6, 1.0e6]
        last_error: Exception | None = None
        for candidate in candidate_rates:
            try:
                self._device.sample_rate = candidate
                self._current_sample_rate = candidate
                # Синхронизируем конфиг, чтобы последующие расчёты FFT использовали реальный sample rate
                self.config.sample_rate = candidate
                time.sleep(0.1)
                if candidate != requested_rate:
                    logger.warning(
                        f"Falling back sample rate to {candidate:.0f} (requested {requested_rate:.0f})"
                    )
                return True
            except Exception as e:
                last_error = e
                logger.warning(f"Failed to set sample_rate={candidate}: {e}")
                time.sleep(0.2)
        logger.error(f"Failed to set sample rate: {last_error}")
        return False
    
    def set_gain(self, gain: float) -> bool:
        if not self._device:
            return False
        
        # Avoid redundant writes
        if self._current_gain and abs(gain - self._current_gain) < 0.1:
            return True
            
        try:
            self._device.gain = gain
            self._current_gain = gain
            return True
        except Exception as e:
            logger.error(f"Failed to set gain: {e}")
            return False
    
    def read_samples(self, num_samples: int) -> NDArray[np.complex64]:
        if not self._device:
            return np.array([], dtype=np.complex64)
        
        # Проверяем нужно ли восстановление
        if self._needs_recovery:
            if self._do_smart_recovery():
                self._needs_recovery = False
            else:
                return np.array([], dtype=np.complex64)
        
        try:
            # Добавляем небольшую задержку для стабильности USB
            time.sleep(self._read_delay)
            
            samples = self._device.read_samples(num_samples)
            self._error_count = 0  # Сброс счётчика при успехе
            self._successful_reads += 1
            return samples.astype(np.complex64)
        except Exception as e:
            self._error_count += 1
            error_str = str(e)
            
            # Детектируем критические ошибки USB
            is_critical = any(x in error_str.lower() for x in 
                            ['libusb', 'access violation', 'io error', 'pipe'])
            
            if self._error_count <= 3:  # Логируем только первые ошибки
                logger.error(f"Failed to read samples (error #{self._error_count}, reads={self._successful_reads}): {e}")
            
            if is_critical or self._error_count >= 3:
                logger.warning(f"Device needs recovery after {self._successful_reads} successful reads")
                self._needs_recovery = True
                self._successful_reads = 0
            
            # При ошибке возвращаем пустой массив и ждём больше
            time.sleep(0.1)
            return np.array([], dtype=np.complex64)
    
    def _do_smart_recovery(self) -> bool:
        """Умное восстановление устройства"""
        if self._recovery_attempts >= self._max_recovery_attempts:
            logger.error("Max recovery attempts reached, device is dead")
            return False
        
        self._recovery_attempts += 1
        logger.info(f"Smart recovery attempt {self._recovery_attempts}/{self._max_recovery_attempts}")
        
        if self._attempt_recovery():
            # Восстанавливаем частоту
            if self._current_freq > 0:
                time.sleep(0.2)
                try:
                    self._device.center_freq = self._current_freq
                    time.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Could not restore frequency: {e}")
            self._recovery_attempts = 0  # Сброс при успехе
            return True
        return False
    
    def get_capabilities(self) -> SDRCapabilities:
        return SDRCapabilities(
            min_freq=24e6,
            max_freq=1766e6,
            min_sample_rate=225001,
            max_sample_rate=3200000,
            min_gain=0,
            max_gain=50,
            name="RTL-SDR"
        )


class HackRFDevice(SDRDevice):
    """Реализация для HackRF устройств"""
    
    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._device = None
    
    def open(self) -> bool:
        try:
            # HackRF требует отдельную библиотеку
            import hackrf
            self._device = hackrf.HackRF()
            self._device.sample_rate = self.config.sample_rate
            self._device.lna_gain = min(self.config.gain, 40)
            self._device.vga_gain = min(self.config.gain, 62)
            logger.info("HackRF opened")
            return True
        except ImportError:
            logger.error("HackRF library not installed. Install with: pip install pyhackrf")
            return False
        except Exception as e:
            logger.error(f"Failed to open HackRF: {e}")
            return False
    
    def close(self) -> None:
        self.stop_streaming()
        if self._device:
            try:
                self._device.close()
            except Exception as e:
                logger.error(f"Error closing HackRF: {e}")
            self._device = None
    
    def set_center_freq(self, freq: float) -> bool:
        if not self._device:
            return False
        try:
            self._device.center_freq = freq
            return True
        except Exception as e:
            logger.error(f"Failed to set frequency: {e}")
            return False
    
    def set_sample_rate(self, rate: float) -> bool:
        if not self._device:
            return False
        try:
            self._device.sample_rate = rate
            return True
        except Exception as e:
            logger.error(f"Failed to set sample rate: {e}")
            return False
    
    def set_gain(self, gain: float) -> bool:
        if not self._device:
            return False
        try:
            self._device.lna_gain = min(gain, 40)
            self._device.vga_gain = min(gain, 62)
            return True
        except Exception as e:
            logger.error(f"Failed to set gain: {e}")
            return False
    
    def read_samples(self, num_samples: int) -> NDArray[np.complex64]:
        if not self._device:
            return np.array([], dtype=np.complex64)
        try:
            # HackRF возвращает int8, конвертируем в complex
            raw = self._device.read_samples(num_samples * 2)
            iq = raw.astype(np.float32).view(np.complex64)
            return iq / 128.0
        except Exception as e:
            logger.error(f"Failed to read samples: {e}")
            return np.array([], dtype=np.complex64)
    
    def get_capabilities(self) -> SDRCapabilities:
        return SDRCapabilities(
            min_freq=1e6,
            max_freq=6e9,
            min_sample_rate=2e6,
            max_sample_rate=20e6,
            min_gain=0,
            max_gain=62,
            name="HackRF"
        )



class LibreSDRDevice(SDRDevice):
    """Реализация для LibreSDR / PlutoSDR / AD9361 через libiio"""
    
    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._ctx = None
        self._phy = None    # ad9361-phy
        self._rx_dev = None # cf-ad9361-lpc
        self._buffer = None
        self._rx_lo = None
        self._buffer_size = 32768
    
    def open(self) -> bool:
        try:
            import iio
        except ImportError:
            logger.error("libiio python bindings not installed. Install with: pip install pylibiio")
            return False
            
        try:
            logger.info("Connecting to LibreSDR/PlutoSDR...")
            
            # Сканируем доступные контексты
            try:
                contexts = iio.scan_contexts()
                logger.info(f"Available IIO contexts: {contexts}")
            except Exception as scan_err:
                logger.warning(f"Failed to scan contexts: {scan_err}")
                contexts = {}
            
            uri = None
            
            # Ищем PlutoSDR/LibreSDR в найденных контекстах
            for ctx_info in contexts:
                ctx_lower = str(ctx_info).lower()
                if any(k in ctx_lower for k in ['pluto', 'libresdr', '192.168.2.1', 'usb']):
                    uri = contexts[ctx_info]
                    logger.info(f"Found matching context: {ctx_info} -> {uri}")
                    break
            
            # Если не нашли, пробуем стандартные URI
            if not uri:
                logger.info("No context found via scan, trying default URIs...")
                # Пробуем различные варианты подключения
                for test_uri in ["usb:", "ip:192.168.2.1", "ip:pluto.local"]:
                    try:
                        logger.info(f"Trying URI: {test_uri}")
                        test_ctx = iio.Context(test_uri)
                        # Проверяем что это действительно AD9361
                        if test_ctx.find_device("ad9361-phy"):
                            uri = test_uri
                            logger.info(f"Successfully connected via: {uri}")
                            break
                        else:
                            logger.debug(f"{test_uri} - no AD9361 device found")
                    except Exception as e:
                        logger.debug(f"{test_uri} - failed: {e}")
                        continue
            
            if not uri:
                logger.error("LibreSDR/PlutoSDR not found. Check USB connection or network (192.168.2.1)")
                return False
                
            self._ctx = iio.Context(uri)
            logger.info(f"IIO Context created: {self._ctx.name}, {self._ctx.description}")
            
            # Список всех устройств для отладки
            devices = [dev.name for dev in self._ctx.devices]
            logger.info(f"Available devices: {devices}")
            
            self._phy = self._ctx.find_device("ad9361-phy")
            self._rx_dev = self._ctx.find_device("cf-ad9361-lpc")
            
            if not self._phy or not self._rx_dev:
                logger.error(f"AD9361 devices not found. Available: {devices}")
                self.close()
                return False
                
            logger.info("AD9361 devices found successfully")
            
            # Настраиваем каналы
            self._rx_lo = self._phy.find_channel("altvoltage0", True) # RX LO
            
            # Включаем RX каналы (IQ)
            for i in range(2): # voltage0 (I), voltage1 (Q)
                 chn = self._rx_dev.find_channel(f"voltage{i}", False)
                 if chn:
                     chn.enabled = True
            
            # Создаем буфер
            self._buffer = iio.Buffer(self._rx_dev, self._buffer_size, False)
            
            # Применяем настройки
            if self.config.center_freq:
                self.set_center_freq(self.config.center_freq)
            else:
                self.set_center_freq(100e6)
                
            self.set_sample_rate(self.config.sample_rate)
            self.set_gain(self.config.gain)
            
            logger.info("LibreSDR/PlutoSDR opened successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to open LibreSDR: {e}", exc_info=True)
            self.close()
            return False
            
    def close(self) -> None:
        self.stop_streaming()
        self._buffer = None
        self._ctx = None
        
    def set_center_freq(self, freq: float) -> bool:
        if not self._rx_lo:
            return False
        try:
            self._rx_lo.attrs['frequency'].value = str(int(freq))
            return True
        except Exception as e:
            logger.error(f"LibreSDR set_freq error: {e}")
            return False
            
    def set_sample_rate(self, rate: float) -> bool:
        if not self._phy:
            return False
        try:
            # AD9361 sample rate is usually set on the baseband
            self._phy.find_channel("voltage0", False).attrs['sampling_frequency'].value = str(int(rate))
            return True
        except Exception as e:
            logger.error(f"LibreSDR set_sample_rate error: {e}")
            return False
            
    def set_gain(self, gain: float) -> bool:
        if not self._phy:
            return False
        try:
            # Set manual gain mode and gain value
            # Note: This is simplified. Might need to specific channel name 'voltage0'
            chn = self._phy.find_channel("voltage0", False)
            if 'gain_control_mode' in chn.attrs:
                chn.attrs['gain_control_mode'].value = 'manual'
            if 'hardwaregain' in chn.attrs:
                chn.attrs['hardwaregain'].value = str(int(gain))
            return True
        except Exception as e:
            logger.error(f"LibreSDR set_gain error: {e}")
            return False
            
    def read_samples(self, num_samples: int) -> NDArray[np.complex64]:
        if not self._buffer:
            return np.zeros(num_samples, dtype=np.complex64)
            
        try:
            self._buffer.refill()
            data = self._buffer.read()
            
            # Данные приходят как int16 I, Q
            # Преобразуем
            samples = np.frombuffer(data, dtype=np.int16)
            
            # Разделяем I и Q (они чередуются)
            # samples[0::2] -> I, samples[1::2] -> Q
            # In case of stereo/2-channels
            
            # Handle potential mismatch in buffer size vs read size
            # Usually iio buffer size is fixed at creation
            
            i_samples = samples[0::2]
            q_samples = samples[1::2]
            
            # Normalize to -1.0 .. 1.0 (12-bit usually, sometimes 16-bit padded)
            # AD9361 ADC is 12-bit
            complex_samples = (i_samples + 1j * q_samples).astype(np.complex64) / 2048.0
            
            return complex_samples
            
        except Exception as e:
            logger.error(f"LibreSDR read error: {e}")
            return np.zeros(num_samples, dtype=np.complex64)
            
    def get_capabilities(self) -> SDRCapabilities:
        return SDRCapabilities(
            min_freq=70e6,
            max_freq=6000e6,
            min_sample_rate=520e3,
            max_sample_rate=61.44e6,
            min_gain=0,
            max_gain=89,
            name="LibreSDR/AD9361"
        )


class USRPDevice(SDRDevice):
    """Реализация для USRP устройств (B200/B210/LibreSDR) через SoapySDR ctypes wrapper"""
    
    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._soapy = None
        self._stream_active = False
    
    def open(self) -> bool:
        try:
            from .soapy_wrapper import SoapySDR, SOAPY_SDR_RX, SOAPY_SDR_CF32
            
            logger.info("Connecting to USRP/LibreSDR device via SoapySDR ctypes wrapper...")
            
            # Создаем SoapySDR wrapper
            self._soapy = SoapySDR()
            
            # Ищем USRP устройство
            devices = self._soapy.enumerate("driver=uhd")
            if not devices:
                logger.error("No USRP devices found via SoapySDR/UHD")
                return False
            
            device_args = devices[0]
            logger.info(f"Found USRP device: {device_args}")
            
            # Пытаемся создать устройство using enumerated args
            # "fx3 is in state 5" error handling preserved
            try:
                self._soapy.make_device(device_args)
            except RuntimeError as e:
                if "fx3 is in state 5" in str(e):
                    logger.error("⚠️ USRP FX3 firmware in bad state (state 5)")
                    logger.error("   Solutions:")
                    logger.error("   1. Reboot your computer (recommended)")
                    logger.error("   2. Try different USB port")
                    logger.error("   3. Update USRP firmware")
                    logger.info("   Falling back to simulated mode...")
                    self._soapy = None
                    return False
                else:
                    raise
            
            # Применяем настройки
            freq = self.config.center_freq if self.config.center_freq else 100e6
            self._soapy.set_frequency(SOAPY_SDR_RX, 0, freq)
            actual_freq = self._soapy.get_frequency(SOAPY_SDR_RX, 0)
            logger.info(f"USRP frequency: {actual_freq/1e6:.3f} MHz")
            
            self._soapy.set_sample_rate(SOAPY_SDR_RX, 0, self.config.sample_rate)
            actual_rate = self._soapy.get_sample_rate(SOAPY_SDR_RX, 0)
            logger.info(f"USRP sample rate: {actual_rate/1e6:.3f} MHz")
            
            self._soapy.set_gain(SOAPY_SDR_RX, 0, self.config.gain)
            actual_gain = self._soapy.get_gain(SOAPY_SDR_RX, 0)
            logger.info(f"USRP gain: {actual_gain} dB")
            
            # Настраиваем поток
            self._soapy.setup_stream(SOAPY_SDR_RX, SOAPY_SDR_CF32, [0])
            self._soapy.activate_stream()
            self._stream_active = True
            
            logger.info("✅ USRP/LibreSDR device opened successfully - REAL DATA STREAMING!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to open USRP: {e}", exc_info=True)
            self.close()
            return False
    
    def close(self) -> None:
        if self._soapy:
            try:
                if self._stream_active:
                    self._soapy.deactivate_stream()
                    self._stream_active = False
                self._soapy.close_stream()
                self._soapy.unmake_device()
            except:
                pass
        self._soapy = None
        logger.info("USRP device closed")
    
    def set_center_freq(self, freq: float) -> bool:
        if not self._soapy:
            return False
        try:
            from .soapy_wrapper import SOAPY_SDR_RX
            return self._soapy.set_frequency(SOAPY_SDR_RX, 0, freq)
        except Exception as e:
            logger.error(f"USRP set_freq error: {e}")
            return False
    
    def set_sample_rate(self, rate: float) -> bool:
        if not self._soapy:
            return False
        try:
            from .soapy_wrapper import SOAPY_SDR_RX
            return self._soapy.set_sample_rate(SOAPY_SDR_RX, 0, rate)
        except Exception as e:
            logger.error(f"USRP set_sample_rate error: {e}")
            return False
    
    def set_gain(self, gain: float) -> bool:
        if not self._soapy:
            return False
        try:
            from .soapy_wrapper import SOAPY_SDR_RX
            return self._soapy.set_gain(SOAPY_SDR_RX, 0, gain)
        except Exception as e:
            logger.error(f"USRP set_gain error: {e}")
            return False
    
    def read_samples(self, num_samples: int) -> NDArray[np.complex64]:
        if not self._soapy or not self._stream_active:
            return np.zeros(num_samples, dtype=np.complex64)
        
        try:
            # Читаем РЕАЛЬНЫЕ данные с USRP через SoapySDR
            samples = self._soapy.read_stream(num_samples, timeout_us=1000000)
            if samples is not None and len(samples) > 0:
                return samples
            else:
                logger.warning("No samples received from USRP")
                return np.zeros(num_samples, dtype=np.complex64)
        except Exception as e:
            logger.error(f"USRP read error: {e}")
            return np.zeros(num_samples, dtype=np.complex64)
    
    def get_capabilities(self) -> SDRCapabilities:
        return SDRCapabilities(
            min_freq=70e6,
            max_freq=6000e6,
            min_sample_rate=200e3,
            max_sample_rate=56e6,  # B200/B210
            min_gain=0,
            max_gain=76,
            name="USRP (B200/B210)"
        )


class SimulatedDevice(SDRDevice):
    """Симулированное устройство для тестирования без реального SDR"""
    
    def __init__(self, config: DeviceConfig):
        super().__init__(config)
        self._center_freq = 100e6
        self._sample_rate = config.sample_rate
        self._noise_floor = -90  # dBm
        self._inject_events = True
        self._last_event_time = 0.0
    
    def open(self) -> bool:
        logger.info("Simulated SDR device opened")
        return True
    
    def close(self) -> None:
        self.stop_streaming()
        logger.info("Simulated SDR device closed")
    
    def set_center_freq(self, freq: float) -> bool:
        self._center_freq = freq
        return True
    
    def set_sample_rate(self, rate: float) -> bool:
        self._sample_rate = rate
        return True
    
    def set_gain(self, gain: float) -> bool:
        return True
    
    def read_samples(self, num_samples: int) -> NDArray[np.complex64]:
        """Генерация симулированных данных с случайными событиями"""
        # Базовый шум
        noise_power = 10 ** (self._noise_floor / 10)
        noise = np.sqrt(noise_power / 2) * (
            np.random.randn(num_samples) + 1j * np.random.randn(num_samples)
        )
        
        samples = noise.astype(np.complex64)
        
        # Случайная инжекция сигналов для тестирования детекции
        if self._inject_events and np.random.random() < 0.05:
            # Создаём синусоидальный сигнал
            t = np.arange(num_samples) / self._sample_rate
            freq_offset = np.random.uniform(-self._sample_rate/4, self._sample_rate/4)
            signal_power = 10 ** (np.random.uniform(-60, -30) / 10)
            signal = np.sqrt(signal_power) * np.exp(2j * np.pi * freq_offset * t)
            
            # Случайная длительность и положение
            start = np.random.randint(0, num_samples // 2)
            duration = np.random.randint(num_samples // 10, num_samples // 2)
            end = min(start + duration, num_samples)
            
            samples[start:end] += signal[start:end].astype(np.complex64)
        
        return samples
    
    def get_capabilities(self) -> SDRCapabilities:
        return SDRCapabilities(
            min_freq=1e6,
            max_freq=6e9,
            min_sample_rate=1e6,
            max_sample_rate=20e6,
            min_gain=0,
            max_gain=50,
            name="Simulated"
        )


def create_device(config: DeviceConfig) -> SDRDevice:
    """Фабрика для создания SDR устройства - ТОЛЬКО реальные устройства"""
    from rf_analyzer.core.config import DeviceType
    
    device_map = {
        DeviceType.RTLSDR: RTLSDRDevice,
        DeviceType.HACKRF: HackRFDevice,
        DeviceType.LIBRESDR: LibreSDRDevice,
        DeviceType.USRP: USRPDevice,
        # DeviceType.SIMULATED убран - только реальные данные!
    }
    
    device_class = device_map.get(config.device_type)
    if not device_class:
        raise ValueError(f"Unknown device type: {config.device_type}. Simulated mode removed - use real SDR only!")
    
    return device_class(config)
