"""
RF Event Analyzer - Modern GUI (PySide6)
"""
from __future__ import annotations

import sys
import logging
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject, Slot
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QStatusBar,
    QHeaderView,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QComboBox,
    QTabWidget,
    QFormLayout,
    QTextEdit,
    QProgressBar,
    QDialog,
    QDialogButtonBox,
    QCheckBox,
    QFrame,
    QSlider,
    QSplitter,
    QSizePolicy,
)
from PySide6.QtGui import QAction, QFont, QColor, QPalette

from rf_analyzer.core.config import AppConfig, DeviceType, FrequencyRange, RFEvent
from rf_analyzer.engine.monitor import RFMonitor, MonitorState
from rf_analyzer.license.license_manager import LicenseManager, LicenseType
from rf_analyzer.reports.generator import ReportGenerator
from rf_analyzer.storage.event_storage import EventStorage
from rf_analyzer.gui.styles import DARK_STYLE, LIGHT_STYLE, COLORS
from rf_analyzer.gui.widgets.waterfall import WaterfallWidget, SpectrumWidget
from rf_analyzer.notifications.telegram_notifier import TelegramConfig, TelegramNotifier

logger = logging.getLogger(__name__)

# Путь к файлу автосохранения настроек
SETTINGS_FILE = Path.home() / ".rf_analyzer" / "settings.yaml"


class StatsCard(QFrame):
    """Карточка статистики"""
    
    def __init__(self, title: str, value: str = "0", parent=None):
        super().__init__(parent)
        self.setObjectName("statsCard")
        self.setStyleSheet("""
            QFrame#statsCard {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3d3d4f, stop:1 #2d2d3d);
                border: 1px solid #4d4d5f;
                border-radius: 12px;
                min-width: 140px;
                min-height: 80px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # Заголовок
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #a1a1aa; font-size: 12px; font-weight: 500;")
        layout.addWidget(title_label)
        
        # Значение
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet("color: #e4e4e7; font-size: 24px; font-weight: 700;")
        layout.addWidget(self.value_label)
    
    def set_value(self, value: str):
        self.value_label.setText(value)
    
    def set_color(self, color: str):
        self.value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 700;")


class StatusIndicator(QWidget):
    """Индикатор статуса с анимацией"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)
        
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: #71717a; font-size: 12px;")
        layout.addWidget(self.dot)
        
        self.label = QLabel("Остановлен")
        self.label.setStyleSheet("color: #a1a1aa; font-weight: 500; font-size: 13px;")
        layout.addWidget(self.label)
        
        # Время работы
        self.uptime_label = QLabel("")
        self.uptime_label.setStyleSheet("color: #71717a; font-size: 12px; margin-left: 8px;")
        layout.addWidget(self.uptime_label)
    
    def set_status(self, text: str, color: str = "#71717a"):
        self.dot.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.label.setText(text)
    
    def set_uptime(self, uptime_text: str):
        if uptime_text:
            self.uptime_label.setText(f"({uptime_text})")
            self.uptime_label.setVisible(True)
        else:
            self.uptime_label.setVisible(False)


class MonitorWorker(QObject):
    """Worker для мониторинга в отдельном потоке"""
    event_detected = Signal(object)  # RFEvent
    state_changed = Signal(str)
    stats_updated = Signal(dict)
    
    def __init__(self, monitor: RFMonitor):
        super().__init__()
        self.monitor = monitor


class LicenseDialog(QDialog):
    """Диалог активации лицензии с современным дизайном"""
    
    def __init__(self, license_mgr: LicenseManager, parent=None):
        super().__init__(parent)
        self.license_mgr = license_mgr
        self.setWindowTitle("Управление лицензией")
        self.setMinimumWidth(450)
        self.setStyleSheet(DARK_STYLE)
        self._setup_ui()
        self._update_status()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Заголовок
        header = QLabel("Управление лицензией")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #60a5fa;")
        layout.addWidget(header)
        
        # Статус карточка
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d3d;
                border: 1px solid #3d3d4f;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        status_layout = QVBoxLayout(status_frame)
        
        self.status_label = QLabel()
        self.status_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        status_layout.addWidget(self.status_label)
        
        self.type_label = QLabel()
        self.type_label.setStyleSheet("color: #a1a1aa;")
        status_layout.addWidget(self.type_label)
        
        self.expires_label = QLabel()
        self.expires_label.setStyleSheet("color: #a1a1aa;")
        status_layout.addWidget(self.expires_label)
        
        self.ranges_label = QLabel()
        self.ranges_label.setStyleSheet("color: #a1a1aa;")
        status_layout.addWidget(self.ranges_label)
        
        self.reports_label = QLabel()
        self.reports_label.setStyleSheet("color: #a1a1aa;")
        status_layout.addWidget(self.reports_label)
        
        layout.addWidget(status_frame)
        
        # Trial кнопка
        self.trial_btn = QPushButton("Начать пробный период (7 дней)")
        self.trial_btn.setMinimumHeight(48)
        self.trial_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1e8e3e, stop:1 #34a853);
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #167a32, stop:1 #1e8e3e);
            }
            QPushButton:disabled {
                background: #3d3d4f;
                color: #71717a;
            }
        """)
        self.trial_btn.clicked.connect(self._start_trial)
        layout.addWidget(self.trial_btn)
        
        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background-color: #3d3d4f;")
        layout.addWidget(sep)
        
        # Активация ключа
        key_label = QLabel("Активация PRO лицензии")
        key_label.setStyleSheet("font-weight: 600; color: #e4e4e7;")
        layout.addWidget(key_label)
        
        key_layout = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("PRO-XXXX-XXXX-XXXX-XXXX")
        self.key_input.setMinimumHeight(44)
        key_layout.addWidget(self.key_input)
        
        self.activate_btn = QPushButton("Активировать")
        self.activate_btn.setMinimumHeight(44)
        self.activate_btn.setMinimumWidth(120)
        self.activate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1a73e8, stop:1 #4285f4);
                border: none;
                border-radius: 8px;
                font-weight: 600;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1557b0, stop:1 #1a73e8);
            }
        """)
        self.activate_btn.clicked.connect(self._activate)
        key_layout.addWidget(self.activate_btn)
        layout.addLayout(key_layout)
        
        layout.addStretch()
        
        # Кнопка закрыть
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.reject)
        layout.addWidget(close_btn)
    
    def _update_status(self):
        status = self.license_mgr.get_status()
        
        if status['status'] == 'active':
            if status['license_type'] == 'trial':
                self.status_label.setText("Trial активен")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #fbbf24;")
            else:
                self.status_label.setText(f"{status['license_type'].upper()} лицензия активна")
                self.status_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #34d399;")
            
            self.type_label.setText(f"Тип: {status['license_type'].upper()}")
            self.expires_label.setText(f"Истекает: {status['expires_at']} ({status['days_remaining']} дн.)")
            self.ranges_label.setText(f"Диапазонов: {status['max_ranges']}")
            self.reports_label.setText(f"Отчётов сегодня: {status['reports_today']}/{status['max_reports_per_day']}")
            self.trial_btn.setEnabled(False)
        elif status['status'] == 'expired':
            self.status_label.setText("Лицензия истекла")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #f87171;")
            self.type_label.setText(f"Тип: {status.get('license_type', 'N/A')}")
            self.expires_label.setText("Продлите лицензию для продолжения работы")
            self.ranges_label.setText("")
            self.reports_label.setText("")
        else:
            self.status_label.setText("Лицензия не активирована")
            self.status_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #fbbf24;")
            self.type_label.setText("")
            self.expires_label.setText("Активируйте пробный период или введите ключ")
            self.ranges_label.setText("")
            self.reports_label.setText("")
    
    def _start_trial(self):
        try:
            self.license_mgr.start_trial()
            QMessageBox.information(self, "Успех", "Пробный период активирован на 7 дней!")
            self._update_status()
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
    
    def _activate(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Ошибка", "Введите ключ лицензии")
            return
        
        try:
            self.license_mgr.activate_license(key)
            QMessageBox.information(self, "Успех", "Лицензия успешно активирована!")
            self._update_status()
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка активации: {e}")


class RangeConfigDialog(QDialog):
    """Диалог настройки диапазона с современным дизайном"""
    
    def __init__(self, freq_range: FrequencyRange | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка диапазона" if freq_range else "Новый диапазон")
        self.setMinimumWidth(400)
        self.setStyleSheet(DARK_STYLE)
        self.freq_range = freq_range
        self._setup_ui()
        
        if freq_range:
            self._load_range(freq_range)
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        
        # Заголовок
        header = QLabel(self.windowTitle())
        header.setStyleSheet("font-size: 18px; font-weight: 700; color: #60a5fa;")
        layout.addWidget(header)
        
        # Форма в карточке
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d3d;
                border: 1px solid #3d3d4f;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        form = QFormLayout(form_frame)
        form.setSpacing(12)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Например: LTE Band 7")
        form.addRow("Название:", self.name_input)
        
        self.start_freq = QDoubleSpinBox()
        self.start_freq.setRange(1, 6000)
        self.start_freq.setDecimals(3)
        self.start_freq.setSuffix(" МГц")
        form.addRow("Начальная частота:", self.start_freq)
        
        self.stop_freq = QDoubleSpinBox()
        self.stop_freq.setRange(1, 6000)
        self.stop_freq.setDecimals(3)
        self.stop_freq.setSuffix(" МГц")
        form.addRow("Конечная частота:", self.stop_freq)
        
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(-120, 20)
        self.threshold.setDecimals(1)
        self.threshold.setSuffix(" дБ")
        self.threshold.setValue(-60)
        form.addRow("Порог срабатывания:", self.threshold)
        
        self.min_duration = QSpinBox()
        self.min_duration.setRange(1, 10000)
        self.min_duration.setSuffix(" мс")
        self.min_duration.setValue(100)
        form.addRow("Мин. длительность:", self.min_duration)
        
        self.enabled = QCheckBox("Диапазон активен")
        self.enabled.setChecked(True)
        form.addRow("", self.enabled)
        
        layout.addWidget(form_frame)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setMinimumWidth(100)
        save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1a73e8, stop:1 #4285f4);
                border: none;
                color: white;
            }
        """)
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    def _load_range(self, freq_range: FrequencyRange):
        self.name_input.setText(freq_range.name)
        self.start_freq.setValue(freq_range.start_freq / 1e6)
        self.stop_freq.setValue(freq_range.stop_freq / 1e6)
        self.threshold.setValue(freq_range.threshold_db)
        self.min_duration.setValue(int(freq_range.min_duration_ms))
        self.enabled.setChecked(freq_range.enabled)
    
    def get_range(self) -> FrequencyRange:
        return FrequencyRange(
            name=self.name_input.text(),
            start_freq=self.start_freq.value() * 1e6,
            stop_freq=self.stop_freq.value() * 1e6,
            threshold_db=self.threshold.value(),
            min_duration_ms=float(self.min_duration.value()),
            enabled=self.enabled.isChecked(),
        )


class MainWindow(QMainWindow):
    """Главное окно приложения с современным дизайном"""

    # Сигналы нужны, чтобы безопасно обновлять UI из фонового потока монитора.
    event_completed = Signal(object)  # RFEvent
    event_active = Signal(object)  # RFEvent
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RF Event Analyzer Pro")
        self.setMinimumSize(1100, 700)
        
        # Компоненты
        self.license_mgr = LicenseManager()
        self.config = self._load_settings()  # Загружаем сохранённые настройки
        self.storage: EventStorage | None = None
        self.monitor: RFMonitor | None = None
        
        # Telegram уведомления - загружаем из сохранённых настроек
        self.telegram_config = self._load_telegram_settings()
        self.telegram_notifier: TelegramNotifier | None = None
        
        # Отслеживание последнего обработанного спектра
        self._last_spectrum_timestamp = 0.0
        
        # Применяем тёмную тему
        self.setStyleSheet(DARK_STYLE)
        
        self._setup_ui()
        self._setup_menu()
        self._setup_statusbar()
        self._setup_timer()

        # Привязываем сигналы событий к обработчикам UI
        self.event_completed.connect(self._on_event_ui)
        self.event_active.connect(self._on_event_active_ui)
        
        # Применяем загруженные настройки к UI
        self._apply_loaded_settings_to_ui()
        
        # Загружаем UI состояния (waterfall, trace hold)
        self._load_ui_state()
        
        # Проверка лицензии
        self._check_license()
        
        logger.info("Application started, settings loaded")

    def _find_event_row(self, key: str) -> int | None:
        """Найти строку в таблице по ключу события (Qt.UserRole)."""
        if not hasattr(self, "events_table") or self.events_table is None:
            return None
        for row in range(self.events_table.rowCount()):
            item = self.events_table.item(row, 1)
            if item and item.data(Qt.UserRole) == key:
                return row
        return None

    def _upsert_event_row(self, event: RFEvent, *, completed: bool) -> None:
        """Добавить/обновить строку события в таблице."""
        import time as _time

        active_key = f"active::{event.range_name}"

        # Для активных событий обновляем одну "живую" строку на диапазон.
        row = None if completed else self._find_event_row(active_key)

        # Для завершённых событий:
        # - если есть активная строка этого диапазона — финализируем её (duration фиксируется),
        # - иначе добавляем новую строку (не затираем историю).
        if completed:
            existing_active = self._find_event_row(active_key)
            if existing_active is not None:
                row = existing_active

        if row is None:
            self.events_table.insertRow(0)
            row = 0

        # Время
        self.events_table.setItem(row, 0, QTableWidgetItem(event.start_time.strftime("%H:%M:%S")))
        # Диапазон + ключ строки
        range_item = QTableWidgetItem(event.range_name)
        range_item.setData(Qt.UserRole, active_key if not completed else f"id::{getattr(event, 'id', None)}")
        self.events_table.setItem(row, 1, range_item)
        # Частота
        self.events_table.setItem(row, 2, QTableWidgetItem(f"{event.center_freq/1e6:.3f}"))
        # Макс. мощность
        self.events_table.setItem(row, 3, QTableWidgetItem(f"{event.max_power_db:.1f}"))

        # Длительность
        if completed and getattr(event, "duration_ms", None) is not None:
            duration_ms = float(event.duration_ms)
        else:
            duration_ms = (_time.time() - event.start_time.timestamp()) * 1000.0
        self.events_table.setItem(row, 4, QTableWidgetItem(f"{duration_ms:.0f}"))

        # Тип
        type_colors = {
            "threshold_exceeded": "#f87171",
            "impulse": "#fbbf24",
            "noise_floor_shift": "#a78bfa",
            "periodic_activity": "#34d399",
            "continuous": "#60a5fa",
        }
        type_item = QTableWidgetItem(event.event_type.value)
        type_item.setForeground(QColor(type_colors.get(event.event_type.value, "#e4e4e7")))
        self.events_table.setItem(row, 5, type_item)

        # Ограничиваем количество строк
        while self.events_table.rowCount() > 100:
            self.events_table.removeRow(self.events_table.rowCount() - 1)
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Заголовок приложения
        header_layout = QHBoxLayout()
        
        title = QLabel("RF Event Analyzer Pro")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #60a5fa;")
        header_layout.addWidget(title)
        
        header_layout.addSpacing(20)
        
        # Кнопки управления мониторингом
        self.start_btn = QPushButton("Старт")
        self.start_btn.setMinimumHeight(36)
        self.start_btn.setMinimumWidth(160)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1e8e3e, stop:1 #34a853);
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #167a32, stop:1 #1e8e3e);
            }
            QPushButton:disabled {
                background: #3d3d4f;
                color: #71717a;
            }
        """)
        self.start_btn.clicked.connect(self._start_monitor)
        header_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("Остановить")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setMinimumWidth(120)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                border: 1px solid #f87171;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                color: #f87171;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.3);
            }
            QPushButton:disabled {
                background: #3d3d4f;
                border-color: #3d3d4f;
                color: #71717a;
            }
        """)
        self.stop_btn.clicked.connect(self._stop_monitor)
        header_layout.addWidget(self.stop_btn)
        
        header_layout.addSpacing(20)
        
        # Быстрые пресеты для обнаружения дронов дальнего полета
        self.preset_buttons = {}
        # Диапазоны для RTL-SDR (до 1.7 GHz) - специально для дронов дальнего полета
        presets = [
            ("ISM 433", 433.0, 434.8, "#f59e0b", "F1"),      # Телеметрия, RC старых дронов
            ("LoRa 868", 863.0, 870.0, "#10b981", "F2"),     # EU телеметрия дальнобойщиков
            ("LoRa 915", 902.0, 928.0, "#3b82f6", "F3"),     # US телеметрия, ELRS дальний
            ("1.2G Video", 1200.0, 1300.0, "#ef4444", "F4"), # Аналоговое видео дальнобойщиков
        ]
        
        for name, start_mhz, stop_mhz, color, hotkey in presets:
            btn = QPushButton(name if not hotkey else f"{name} ({hotkey})")
            btn.setMinimumWidth(70)
            btn.setMaximumWidth(90)
            btn.setMinimumHeight(36)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(61, 61, 79, 0.8);
                    border: 1px solid {color};
                    border-radius: 6px;
                    color: {color};
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: rgba(61, 61, 79, 1.0);
                    border: 2px solid {color};
                }}
                QPushButton:pressed {{
                    background-color: {color};
                    color: #1e1e2e;
                }}
                QPushButton:disabled {{
                    background: #3d3d4f;
                    border-color: #4d4d5f;
                    color: #71717a;
                }}
            """)
            btn.clicked.connect(lambda checked, s=start_mhz, e=stop_mhz, n=name: self._switch_to_preset(n, s, e))
            btn.setEnabled(False)  # Включаем только когда мониторинг активен
            header_layout.addWidget(btn)
            self.preset_buttons[name] = btn
            
            # Добавляем горячую клавишу
            if hotkey:
                from PySide6.QtGui import QShortcut, QKeySequence
                shortcut = QShortcut(QKeySequence(hotkey), self)
                shortcut.activated.connect(lambda s=start_mhz, e=stop_mhz, n=name: self._switch_to_preset(n, s, e))
        
        header_layout.addStretch()
        
        self.status_indicator = StatusIndicator()
        header_layout.addWidget(self.status_indicator)
        
        layout.addLayout(header_layout)
        
        # Табы с иконками
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Таб мониторинга
        monitor_tab = QWidget()
        tabs.addTab(monitor_tab, "Мониторинг")
        self._setup_monitor_tab(monitor_tab)
        
        # Таб настроек
        settings_tab = QWidget()
        tabs.addTab(settings_tab, "Настройки")
        self._setup_settings_tab(settings_tab)
        
        # Таб отчётов
        reports_tab = QWidget()
        tabs.addTab(reports_tab, "Отчёты")
        self._setup_reports_tab(reports_tab)
    
    def _setup_monitor_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setSpacing(16)
        
        # FPS ограничение для GUI
        
        self._last_gui_update = 0.0
        self._min_update_interval = 1.0 / 60.0  # 60 FPS - соответствует скорости RTL-SDR        # Таймер обновления состояния маркеров
        self._marker_update_timer = QTimer()
        self._marker_update_timer.timeout.connect(self._update_marker_buttons)
        self._marker_update_timer.start(500)  # Обновление каждые 500 мс
        
        # Словарь для хранения порогов для каждого пресета
        self._preset_thresholds = {}
        self._current_preset_name = None
        
        # Панель управления
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d3d;
                border: 1px solid #3d3d4f;
                border-radius: 12px;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(16, 12, 16, 12)
        
        # Слайдер усиления
        gain_label = QLabel("Gain:")
        gain_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        control_layout.addWidget(gain_label)
        
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setMinimum(0)
        self.gain_slider.setMaximum(50)
        self.gain_slider.setValue(self.config.device.gain)
        self.gain_slider.setMaximumWidth(120)
        self.gain_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #3d3d4f;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #34d399;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #6ee7b7;
            }
        """)
        self.gain_slider.valueChanged.connect(self._on_gain_changed)
        control_layout.addWidget(self.gain_slider)
        
        self.gain_value_label = QLabel(f"{self.config.device.gain:.0f} дБ")
        self.gain_value_label.setStyleSheet("color: #34d399; font-size: 12px; font-weight: 600; min-width: 50px;")
        control_layout.addWidget(self.gain_value_label)
        
        control_layout.addSpacing(20)
        
        # Слайдер порога детекции
        threshold_label = QLabel("Порог:")
        threshold_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        control_layout.addWidget(threshold_label)
        
        self.threshold_slider = QSlider(Qt.Horizontal)
        self.threshold_slider.setMinimum(-100)
        self.threshold_slider.setMaximum(100)
        self.threshold_slider.setValue(-60)
        self.threshold_slider.setMaximumWidth(150)
        self.threshold_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #3d3d4f;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #f87171;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #fca5a5;
            }
        """)
        self.threshold_slider.valueChanged.connect(self._on_threshold_changed)
        control_layout.addWidget(self.threshold_slider)
        
        self.threshold_value_label = QLabel("-60 дБ")
        self.threshold_value_label.setStyleSheet("color: #f87171; font-size: 12px; font-weight: 600; min-width: 60px;")
        control_layout.addWidget(self.threshold_value_label)
        
        control_layout.addSpacing(20)
        
        # Переключатель waterfall
        self.waterfall_enabled = QCheckBox("Waterfall")
        self.waterfall_enabled.setChecked(True)
        self.waterfall_enabled.setStyleSheet("""   
            QCheckBox {
                color: #a1a1aa;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:checked {
                background-color: #34d399;
                border: 1px solid #34d399;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #3d3d4f;
                border: 1px solid #71717a;
                border-radius: 3px;
            }
        """)
        self.waterfall_enabled.stateChanged.connect(self._toggle_waterfall)
        control_layout.addWidget(self.waterfall_enabled)
        
        control_layout.addSpacing(20)
        
        # Trace Hold переключатель
        self.trace_hold_enabled = QCheckBox("Trace Hold")
        self.trace_hold_enabled.setChecked(True)  # По умолчанию включен
        self.trace_hold_enabled.setStyleSheet("""   
            QCheckBox {
                color: #a1a1aa;
                font-size: 12px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:checked {
                background-color: #f87171;
                border: 1px solid #f87171;
                border-radius: 3px;
            }
            QCheckBox::indicator:unchecked {
                background-color: #3d3d4f;
                border: 1px solid #71717a;
                border-radius: 3px;
            }
        """)
        self.trace_hold_enabled.stateChanged.connect(self._toggle_trace_hold)
        control_layout.addWidget(self.trace_hold_enabled)
        
        # Кнопка сброса Trace Hold
        self.trace_hold_reset_btn = QPushButton("Сброс")
        self.trace_hold_reset_btn.setMinimumWidth(50)
        self.trace_hold_reset_btn.setMaximumWidth(70)
        self.trace_hold_reset_btn.setMinimumHeight(24)
        self.trace_hold_reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d4f;
                border: 1px solid #71717a;
                border-radius: 4px;
                color: #f87171;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #4d4d5f;
                border-color: #f87171;
            }
            QPushButton:pressed {
                background-color: #2d2d3d;
            }
        """)
        self.trace_hold_reset_btn.clicked.connect(self._reset_trace_hold)
        control_layout.addWidget(self.trace_hold_reset_btn)
        
        control_layout.addSpacing(20)
        
        # Управление маркерами
        markers_label = QLabel("Маркеры:")
        markers_label.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        control_layout.addWidget(markers_label)
        
        # Кнопка добавления маркера на заданной частоте
        self.marker_add_btn = QPushButton("Добавить")
        self.marker_add_btn.setMinimumWidth(70)
        self.marker_add_btn.setMaximumWidth(90)
        self.marker_add_btn.setMinimumHeight(24)
        self.marker_add_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d4f;
                border: 1px solid #71717a;
                border-radius: 4px;
                color: #22c55e;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #4d4d5f;
                border-color: #22c55e;
            }
            QPushButton:pressed {
                background-color: #2d2d3d;
            }
        """)
        self.marker_add_btn.clicked.connect(self._add_marker_dialog)
        control_layout.addWidget(self.marker_add_btn)
        
        # Кнопка удаления выбранного маркера
        self.marker_delete_btn = QPushButton("Удалить")
        self.marker_delete_btn.setMinimumWidth(60)
        self.marker_delete_btn.setMaximumWidth(80)
        self.marker_delete_btn.setMinimumHeight(24)
        self.marker_delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d4f;
                border: 1px solid #71717a;
                border-radius: 4px;
                color: #22c55e;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #4d4d5f;
                border-color: #22c55e;
            }
            QPushButton:pressed {
                background-color: #2d2d3d;
            }
            QPushButton:disabled {
                color: #71717a;
                border-color: #71717a;
            }
        """)
        self.marker_delete_btn.clicked.connect(self._delete_selected_marker)
        self.marker_delete_btn.setEnabled(False)
        control_layout.addWidget(self.marker_delete_btn)
        
        # Кнопка очистки всех маркеров
        self.markers_clear_btn = QPushButton("Очистить все")
        self.markers_clear_btn.setMinimumWidth(80)
        self.markers_clear_btn.setMaximumWidth(100)
        self.markers_clear_btn.setMinimumHeight(24)
        self.markers_clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d4f;
                border: 1px solid #71717a;
                border-radius: 4px;
                color: #22c55e;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #4d4d5f;
                border-color: #22c55e;
            }
            QPushButton:pressed {
                background-color: #2d2d3d;
            }
            QPushButton:disabled {
                color: #71717a;
                border-color: #71717a;
            }
        """)
        self.markers_clear_btn.clicked.connect(self._clear_all_markers)
        self.markers_clear_btn.setEnabled(False)
        control_layout.addWidget(self.markers_clear_btn)
        
        control_layout.addSpacing(10)
        
        self.current_range_label = QLabel("Диапазон: —")
        self.current_range_label.setStyleSheet("color: #a1a1aa;")
        control_layout.addWidget(self.current_range_label)
        
        layout.addWidget(control_frame)
        
        # Splitter для спектра и таблицы
        splitter = QSplitter(Qt.Vertical)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3d3d4f;
                height: 3px;
            }
        """)
        
        # Виджеты визуализации спектра
        spectrum_frame = QFrame()
        spectrum_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d3d;
                border: 1px solid #3d3d4f;
                border-radius: 8px;
            }
        """)
        spectrum_layout = QVBoxLayout(spectrum_frame)
        spectrum_layout.setContentsMargins(8, 8, 8, 8)
        spectrum_layout.setSpacing(2)  # Минимальный зазор
        
        # Спектр
        spectrum_group = QGroupBox("")
        spectrum_group.setStyleSheet("QGroupBox { border: none; padding: 0px; margin: 0px; }")
        spectrum_group_layout = QVBoxLayout(spectrum_group)
        spectrum_group_layout.setContentsMargins(0, 0, 0, 0)
        spectrum_group_layout.setSpacing(0)
        
        # Заголовок
        spectrum_title = QLabel("Спектр")
        spectrum_title.setStyleSheet("color: #60a5fa; font-size: 12px; font-weight: 600; padding: 2px;")
        spectrum_group_layout.addWidget(spectrum_title)
        
        self.spectrum_widget = SpectrumWidget()
        self.spectrum_widget.setMinimumHeight(200)
        spectrum_group_layout.addWidget(self.spectrum_widget)
        spectrum_layout.addWidget(spectrum_group)
        
        # Waterfall под спектром
        waterfall_group = QGroupBox("")
        waterfall_group.setStyleSheet("QGroupBox { border: none; padding: 0px; margin: 0px; }")
        waterfall_group_layout = QVBoxLayout(waterfall_group)
        waterfall_group_layout.setContentsMargins(0, 0, 0, 0)
        waterfall_group_layout.setSpacing(0)
        
        # Заголовок
        waterfall_title = QLabel("Waterfall")
        waterfall_title.setStyleSheet("color: #60a5fa; font-size: 12px; font-weight: 600; padding: 2px;")
        waterfall_group_layout.addWidget(waterfall_title)
        
        self.waterfall_widget = WaterfallWidget()
        self.waterfall_widget.setMinimumHeight(150)
        waterfall_group_layout.addWidget(self.waterfall_widget)
        spectrum_layout.addWidget(waterfall_group)
        
        splitter.addWidget(spectrum_frame)
        
        # Таблица событий
        events_group = QGroupBox("Последние события")
        events_layout = QVBoxLayout(events_group)
        
        self.events_table = QTableWidget()
        self.events_table.setColumnCount(6)
        self.events_table.setHorizontalHeaderLabels([
            "Время", "Диапазон", "Частота (МГц)", "Макс. (дБ)", "Длит. (мс)", "Тип"
        ])
        self.events_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.events_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.events_table.setAlternatingRowColors(True)
        self.events_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.events_table.verticalHeader().setVisible(False)
        events_layout.addWidget(self.events_table)
        
        splitter.addWidget(events_group)
        
        # Пропорции splitter'а
        splitter.setSizes([250, 300])
        
        layout.addWidget(splitter)
    
    def _setup_settings_tab(self, parent: QWidget):
        # Создаём scroll area для адаптивности
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        
        # Две колонки настроек
        columns = QHBoxLayout()
        columns.setSpacing(16)
        
        # Левая колонка - устройство
        device_group = QGroupBox("SDR устройство")
        device_layout = QFormLayout(device_group)
        device_layout.setSpacing(12)
        
        self.device_combo = QComboBox()
        self.device_combo.addItems(["RTL-SDR", "HackRF", "LibreSDR/PlutoSDR", "USRP (B200/B210)"])
        self.device_combo.setCurrentIndex(3)  # USRP по умолчанию
        device_layout.addRow("Тип:", self.device_combo)
        
        self.sample_rate = QComboBox()
        self.sample_rate.addItems(["1.0", "2.0", "2.4", "3.2"])
        self.sample_rate.setCurrentIndex(2)
        device_layout.addRow("Rate (МГц):", self.sample_rate)
        
        self.gain_spin = QSpinBox()
        self.gain_spin.setRange(0, 50)
        self.gain_spin.setValue(40)
        self.gain_spin.setSuffix(" dB")
        device_layout.addRow("Усил.:", self.gain_spin)
        
        columns.addWidget(device_group)
        
        # Правая колонка - детекция
        detect_group = QGroupBox("Параметры детекции")
        detect_layout = QFormLayout(detect_group)
        detect_layout.setSpacing(12)
        
        self.fft_size = QComboBox()
        self.fft_size.addItems(["256", "512", "1024", "2048", "4096"])
        # Устанавливаем текущий FFT size из конфигурации
        fft_sizes = [256, 512, 1024, 2048, 4096]
        try:
            current_fft_idx = fft_sizes.index(self.config.detection.fft_size)
            self.fft_size.setCurrentIndex(current_fft_idx)
        except ValueError:
            self.fft_size.setCurrentIndex(2)  # default 1024
        detect_layout.addRow("FFT размер:", self.fft_size)
        
        # Информация о порогах
        info_label = QLabel(
            "<span style='color: #71717a; font-size: 10px;'>"
            "ℹ️ <b>Порог импульса</b> - превышение над шумом (дБ)<br>"
            "📊 <b>Порог диапазона</b> - абсолютный уровень (настраивается в таблице ниже)"
            "</span>"
        )
        info_label.setWordWrap(True)
        detect_layout.addRow("", info_label)
        
        self.impulse_threshold = QDoubleSpinBox()
        self.impulse_threshold.setRange(5, 50)
        self.impulse_threshold.setValue(self.config.detection.impulse_threshold_db)
        self.impulse_threshold.setSuffix(" дБ (над шумом)")
        self.impulse_threshold.valueChanged.connect(self._on_detection_setting_changed)
        detect_layout.addRow("Порог имп.:", self.impulse_threshold)
        
        self.noise_avg_spin = QSpinBox()
        self.noise_avg_spin.setRange(10, 500)
        self.noise_avg_spin.setValue(self.config.detection.noise_floor_averaging)
        self.noise_avg_spin.valueChanged.connect(self._on_detection_setting_changed)
        detect_layout.addRow("Усред. шума:", self.noise_avg_spin)
        
        columns.addWidget(detect_group)
        layout.addLayout(columns)
        
        # Группа настроек отображения (Y-ось мощности)
        display_group = QGroupBox("Отображение спектра")
        display_layout = QFormLayout(display_group)
        display_layout.setSpacing(12)
        
        self.min_power_spin = QDoubleSpinBox()
        self.min_power_spin.setRange(-150, 50)
        self.min_power_spin.setValue(-100)  # Дефолтное значение
        self.min_power_spin.setSuffix(" дБ")
        self.min_power_spin.setDecimals(0)
        self.min_power_spin.setSingleStep(10)
        self.min_power_spin.valueChanged.connect(self._on_power_range_changed)
        display_layout.addRow("Мин. мощность (Y):", self.min_power_spin)
        
        self.max_power_spin = QDoubleSpinBox()
        self.max_power_spin.setRange(-100, 100)
        self.max_power_spin.setValue(60)  # Дефолтное значение
        self.max_power_spin.setSuffix(" дБ")
        self.max_power_spin.setDecimals(0)
        self.max_power_spin.setSingleStep(10)
        self.max_power_spin.valueChanged.connect(self._on_power_range_changed)
        display_layout.addRow("Макс. мощность (Y):", self.max_power_spin)
        
        # Подсказка
        power_info = QLabel(
            "<span style='color: #71717a; font-size: 10px;'>"
            "ℹ️ Настройте диапазон оси Y для лучшей визуализации слабых сигналов"
            "</span>"
        )
        power_info.setWordWrap(True)
        display_layout.addRow("", power_info)
        
        layout.addWidget(display_group)
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(parent)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Диапазоны
        ranges_group = QGroupBox("Частотные диапазоны")
        ranges_layout = QVBoxLayout(ranges_group)
        
        self.ranges_table = QTableWidget()
        self.ranges_table.setColumnCount(5)
        self.ranges_table.setHorizontalHeaderLabels([
            "Название", "Начало (МГц)", "Конец (МГц)", "Порог (дБ)", "Статус"
        ])
        self.ranges_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ranges_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.ranges_table.verticalHeader().setVisible(False)
        self.ranges_table.setAlternatingRowColors(True)
        ranges_layout.addWidget(self.ranges_table)
        
        ranges_btn_layout = QHBoxLayout()
        
        add_range_btn = QPushButton("Добавить")
        add_range_btn.clicked.connect(self._add_range)
        ranges_btn_layout.addWidget(add_range_btn)
        
        edit_range_btn = QPushButton("Редактировать")
        edit_range_btn.clicked.connect(self._edit_range)
        ranges_btn_layout.addWidget(edit_range_btn)
        
        del_range_btn = QPushButton("Удалить")
        del_range_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.2);
                border: 1px solid #f87171;
                color: #f87171;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.3);
            }
        """)
        del_range_btn.clicked.connect(self._delete_range)
        ranges_btn_layout.addWidget(del_range_btn)
        
        ranges_btn_layout.addStretch()
        
        load_btn = QPushButton("Загрузить")
        load_btn.clicked.connect(self._load_config)
        ranges_btn_layout.addWidget(load_btn)
        
        save_btn = QPushButton("Сохранить")
        save_btn.clicked.connect(self._save_config)
        ranges_btn_layout.addWidget(save_btn)
        
        apply_btn = QPushButton("Применить настройки")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(34, 197, 94, 0.2);
                border: 1px solid #22c55e;
                color: #22c55e;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: rgba(34, 197, 94, 0.3);
            }
        """)
        apply_btn.clicked.connect(self._apply_settings)
        ranges_btn_layout.addWidget(apply_btn)
        
        ranges_layout.addLayout(ranges_btn_layout)
        layout.addWidget(ranges_group)
        
        # Настройки уведомлений Telegram
        telegram_group = QGroupBox("Telegram уведомления")
        telegram_layout = QFormLayout(telegram_group)
        telegram_layout.setSpacing(10)
        
        self.telegram_enabled = QCheckBox("Включить уведомления")
        telegram_layout.addRow(self.telegram_enabled)
        
        self.telegram_token = QLineEdit()
        self.telegram_token.setPlaceholderText("123456789:ABCdefGHIjklMNOpqrsTUVwxyz")
        self.telegram_token.setEchoMode(QLineEdit.Password)
        telegram_layout.addRow("Bot Token:", self.telegram_token)
        
        self.telegram_chat_id = QLineEdit()
        self.telegram_chat_id.setPlaceholderText("-1001234567890")
        telegram_layout.addRow("Chat ID:", self.telegram_chat_id)
        
        self.telegram_min_power = QDoubleSpinBox()
        self.telegram_min_power.setRange(-120, 100)
        self.telegram_min_power.setValue(-100)  # Высокий порог по умолчанию
        self.telegram_min_power.setSuffix(" дБ")
        telegram_layout.addRow("Мин. уровень:", self.telegram_min_power)
        
        # Интервал уведомлений
        self.telegram_cooldown = QComboBox()
        self.telegram_cooldown.addItem("5 секунд", 5)
        self.telegram_cooldown.addItem("10 секунд", 10)
        self.telegram_cooldown.addItem("30 секунд", 30)
        self.telegram_cooldown.addItem("60 секунд", 60)
        self.telegram_cooldown.setCurrentIndex(0)  # По умолчанию 5 секунд
        telegram_layout.addRow("Интервал уведомлений:", self.telegram_cooldown)
        
        # Подключаем обработчики для динамического применения
        self.telegram_enabled.stateChanged.connect(self._apply_telegram_settings_dynamic)
        self.telegram_token.textChanged.connect(self._apply_telegram_settings_dynamic)
        self.telegram_chat_id.textChanged.connect(self._apply_telegram_settings_dynamic)
        self.telegram_min_power.valueChanged.connect(self._apply_telegram_settings_dynamic)
        self.telegram_cooldown.currentIndexChanged.connect(self._apply_telegram_settings_dynamic)
        
        telegram_btn_layout = QHBoxLayout()
        test_telegram_btn = QPushButton("Тест соединения")
        test_telegram_btn.clicked.connect(self._test_telegram)
        telegram_btn_layout.addWidget(test_telegram_btn)
        telegram_btn_layout.addStretch()
        telegram_layout.addRow(telegram_btn_layout)
        
        layout.addWidget(telegram_group)
        
        self._update_ranges_table()
    
    def _setup_reports_tab(self, parent: QWidget):
        layout = QVBoxLayout(parent)
        layout.setSpacing(16)
        
        # Параметры отчёта в карточке
        params_frame = QFrame()
        params_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d3d;
                border: 1px solid #3d3d4f;
                border-radius: 12px;
            }
        """)
        params_layout = QVBoxLayout(params_frame)
        params_layout.setContentsMargins(20, 20, 20, 20)
        
        params_title = QLabel("Параметры отчёта")
        params_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #60a5fa;")
        params_layout.addWidget(params_title)
        
        form = QFormLayout()
        form.setSpacing(12)
        
        # Период: дни, часы, минуты
        period_layout = QHBoxLayout()
        period_layout.setSpacing(8)
        
        self.report_days = QSpinBox()
        self.report_days.setRange(0, 365)
        self.report_days.setValue(7)
        self.report_days.setSuffix(" дн.")
        self.report_days.setMinimumWidth(100)
        period_layout.addWidget(self.report_days)
        
        self.report_hours = QSpinBox()
        self.report_hours.setRange(0, 23)
        self.report_hours.setValue(0)
        self.report_hours.setSuffix(" ч.")
        self.report_hours.setMinimumWidth(90)
        period_layout.addWidget(self.report_hours)
        
        self.report_minutes = QSpinBox()
        self.report_minutes.setRange(0, 59)
        self.report_minutes.setValue(0)
        self.report_minutes.setSuffix(" мин.")
        self.report_minutes.setMinimumWidth(90)
        period_layout.addWidget(self.report_minutes)
        
        period_layout.addStretch()
        form.addRow("Период:", period_layout)
        
        # Подключаем обработчики изменения значений для автообновления статистики
        self.report_days.valueChanged.connect(self._on_report_period_changed)
        self.report_hours.valueChanged.connect(self._on_report_period_changed)
        self.report_minutes.valueChanged.connect(self._on_report_period_changed)
        
        # Быстрый выбор периода
        quick_select_layout = QHBoxLayout()
        quick_select_layout.setSpacing(8)
        
        quick_periods = [
            ("1 час", 0, 1, 0),
            ("6 часов", 0, 6, 0),
            ("1 день", 1, 0, 0),
            ("7 дней", 7, 0, 0),
            ("30 дней", 30, 0, 0),
        ]
        
        for label, d, h, m in quick_periods:
            btn = QPushButton(label)
            btn.setMaximumWidth(80)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3d3d4f;
                    border: 1px solid #4d4d5f;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 12px;
                    color: #e4e4e7;
                }
                QPushButton:hover {
                    background-color: #4d4d5f;
                    border-color: #60a5fa;
                }
            """)
            btn.clicked.connect(lambda checked, days=d, hours=h, mins=m: self._set_report_period(days, hours, mins))
            quick_select_layout.addWidget(btn)
        
        quick_select_layout.addStretch()
        form.addRow("Быстрый выбор:", quick_select_layout)
        
        self.report_format = QComboBox()
        self.report_format.addItems(["PDF отчёт", "HTML отчёт", "CSV данные"])
        form.addRow("Формат:", self.report_format)
        
        self.report_title = QLineEdit("Отчёт о RF-событиях")
        form.addRow("Заголовок:", self.report_title)
        
        params_layout.addLayout(form)
        layout.addWidget(params_frame)
        
        # Кнопка генерации
        generate_btn = QPushButton("Сгенерировать отчёт")
        generate_btn.setMinimumHeight(50)
        generate_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1a73e8, stop:1 #4285f4);
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                color: white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1557b0, stop:1 #1a73e8);
            }
        """)
        generate_btn.clicked.connect(self._generate_report)
        layout.addWidget(generate_btn)
        
        # Статистика
        stats_group = QGroupBox("Статистика за выбранный период")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)
        self.stats_text.setStyleSheet("""
            QTextEdit {
                font-family: "Consolas", "Monaco", monospace;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        stats_layout.addWidget(self.stats_text)
        
        layout.addWidget(stats_group)
        layout.addStretch()
    
    def _setup_menu(self):
        menubar = self.menuBar()
        
        # Файл
        file_menu = menubar.addMenu("Файл")
        
        load_action = QAction("Загрузить конфиг...", self)
        load_action.triggered.connect(self._load_config)
        file_menu.addAction(load_action)
        
        save_action = QAction("Сохранить конфиг...", self)
        save_action.triggered.connect(self._save_config)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Лицензия
        license_menu = menubar.addMenu("Лицензия")
        
        license_action = QAction("Управление лицензией...", self)
        license_action.triggered.connect(self._show_license_dialog)
        license_menu.addAction(license_action)
        
        # Помощь
        help_menu = menubar.addMenu("Помощь")
        
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_statusbar(self):
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        
        self.license_status = QLabel()
        self.license_status.setStyleSheet("padding: 0 12px;")
        self.statusbar.addPermanentWidget(self.license_status)
        
        self._update_license_status()
    
    def _setup_timer(self):
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_stats)
        self.update_timer.start(200)
    
    def _check_license(self):
        # Программа теперь бесплатная - просто обновляем статус
        self._update_license_status()
    
    def _update_license_status(self):
        # Программа теперь бесплатная и полнофункциональная
        self.license_status.setText("FULL VERSION")
        self.license_status.setStyleSheet("color: #34d399; padding: 0 12px;")
    
    def _update_ranges_table(self, apply_to_monitor: bool = True):
        self.ranges_table.setRowCount(len(self.config.ranges))
        
        for i, r in enumerate(self.config.ranges):
            self.ranges_table.setItem(i, 0, QTableWidgetItem(r.name))
            self.ranges_table.setItem(i, 1, QTableWidgetItem(f"{r.start_freq/1e6:.3f}"))
            self.ranges_table.setItem(i, 2, QTableWidgetItem(f"{r.stop_freq/1e6:.3f}"))
            self.ranges_table.setItem(i, 3, QTableWidgetItem(f"{r.threshold_db:.1f}"))
            
            status_item = QTableWidgetItem("Активен" if r.enabled else "Отключён")
            status_item.setForeground(QColor("#34d399" if r.enabled else "#71717a"))
            self.ranges_table.setItem(i, 4, status_item)
        
        # Автоматически применяем изменения диапазонов к работающему монитору
        if apply_to_monitor:
            self._apply_ranges_to_monitor()
    
    def _add_range(self):
        # Программа теперь бесплатная - нет ограничений
        dialog = RangeConfigDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            new_range = dialog.get_range()
            # Проверяем на нестабильные частоты для FC0012
            if self._check_unstable_frequency(new_range):
                self.config.ranges.append(new_range)
                self._update_ranges_table()
    
    def _edit_range(self):
        row = self.ranges_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Выбор", "Выберите диапазон для редактирования")
            return
        
        dialog = RangeConfigDialog(self.config.ranges[row], parent=self)
        if dialog.exec() == QDialog.Accepted:
            new_range = dialog.get_range()
            # Проверяем на нестабильные частоты
            if self._check_unstable_frequency(new_range):
                self.config.ranges[row] = new_range
                self._update_ranges_table()
    
    def _check_unstable_frequency(self, freq_range: FrequencyRange) -> bool:
        """Проверить диапазон на нестабильные частоты и предупредить пользователя"""
        # Нестабильные зоны для FC0012 (самый распространённый дешёвый тюнер)
        unstable_zones = [
            (580e6, 800e6, "580-800 МГц (нестабильная зона FC0012)"),
        ]
        
        center_freq = freq_range.center_freq
        
        for low, high, description in unstable_zones:
            if low <= center_freq <= high:
                reply = QMessageBox.warning(
                    self, "Предупреждение о частоте",
                    f"Центральная частота {center_freq/1e6:.1f} МГц находится в нестабильной зоне:\n"
                    f"• {description}\n\n"
                    f"Тюнер FC0012 может работать нестабильно на этих частотах.\n\n"
                    f"Рекомендуемые диапазоны:\n"
                    f"• 88-108 МГц (FM радио)\n"
                    f"• 400-470 МГц (UHF)\n"
                    f"• 860-930 МГц (GSM/LTE)\n\n"
                    f"Всё равно добавить этот диапазон?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                return reply == QMessageBox.Yes
        
        return True  # Частота в стабильной зоне
    
    def _delete_range(self):
        row = self.ranges_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Выбор", "Выберите диапазон для удаления")
            return
        
        reply = QMessageBox.question(
            self, "Удаление",
            f"Удалить диапазон «{self.config.ranges[row].name}»?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            del self.config.ranges[row]
            self._update_ranges_table()
    
    def _load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Загрузить конфигурацию",
            "", "YAML Files (*.yaml *.yml)"
        )
        if path:
            try:
                self.config = AppConfig.load(Path(path))
                self._update_ranges_table()
                self.statusbar.showMessage(f"Конфигурация загружена: {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить: {e}")
    
    def _save_config(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить конфигурацию",
            "config.yaml", "YAML Files (*.yaml *.yml)"
        )
        if path:
            try:
                self.config.save(Path(path))
                self.statusbar.showMessage(f"Конфигурация сохранена: {path}", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")
    
    def _apply_settings(self):
        """Применить настройки из GUI к конфигурации"""
        # Применяем настройки устройства
        device_map = {
            0: DeviceType.RTLSDR,
            1: DeviceType.HACKRF,
            2: DeviceType.LIBRESDR,
            3: DeviceType.USRP,
        }
        self.config.device.device_type = device_map[self.device_combo.currentIndex()]
        
        sample_rates = [1.0e6, 2.0e6, 2.4e6, 3.2e6]
        self.config.device.sample_rate = sample_rates[self.sample_rate.currentIndex()]
        self.config.device.gain = self.gain_spin.value()
        
        # Применяем настройки детекции
        self.config.detection.impulse_threshold_db = self.impulse_threshold.value()
        self.config.detection.noise_floor_averaging = self.noise_avg_spin.value()
        fft_sizes = [256, 512, 1024, 2048, 4096]
        self.config.detection.fft_size = fft_sizes[self.fft_size.currentIndex()]
        
        # Если монитор работает - применяем настройки динамически
        if self.monitor and self.monitor.state == MonitorState.RUNNING:
            try:
                # Обновляем конфигурацию детектора
                if hasattr(self.monitor, '_detector') and self.monitor._detector:
                    self.monitor._detector.config = self.config.detection
                
                # Обновляем конфигурацию процессора
                if hasattr(self.monitor, '_processor') and self.monitor._processor:
                    self.monitor._processor.config = self.config.detection
                
                self.statusbar.showMessage("Настройки применены к работающему мониторингу", 3000)
            except Exception as e:
                logger.error(f"Failed to apply settings dynamically: {e}")
                QMessageBox.warning(
                    self, "Настройки применены",
                    "Настройки сохранены, но для полного применения\n"
                    "рекомендуется перезапустить мониторинг."
                )
        else:
            self.statusbar.showMessage("Настройки применены", 3000)
    
    def _on_detection_setting_changed(self):
        """Обработчик изменения настроек детекции - применяем динамически"""
        # Обновляем конфигурацию всегда
        self.config.detection.impulse_threshold_db = self.impulse_threshold.value()
        self.config.detection.noise_floor_averaging = self.noise_avg_spin.value()
        
        if self.monitor and self.monitor.state == MonitorState.RUNNING:
            try:
                logger.info(f"Detection settings changed: impulse_threshold={self.impulse_threshold.value()}dB, "
                           f"noise_averaging={self.noise_avg_spin.value()} spectrums")
                
                # Применяем к детектору
                if hasattr(self.monitor, '_detector') and self.monitor._detector:
                    self.monitor._detector.config = self.config.detection
                    logger.info(f"Applied to detector: threshold={self.monitor._detector.config.impulse_threshold_db}dB")
                
                # Применяем к процессору
                if hasattr(self.monitor, '_processor') and self.monitor._processor:
                    self.monitor._processor.config = self.config.detection
                    logger.info("Applied to processor")
                
            except Exception as e:
                logger.error(f"Failed to apply detection settings: {e}", exc_info=True)
    
    def _on_power_range_changed(self):
        """Обработчик изменения диапазона мощности для отображения"""
        min_power = self.min_power_spin.value()
        max_power = self.max_power_spin.value()
        
        # Проверка корректности диапазона
        if min_power >= max_power:
            logger.warning(f"Invalid power range: min={min_power} >= max={max_power}")
            return
        
        # Применяем к виджетам спектра и водопада
        if hasattr(self, 'spectrum_widget') and self.spectrum_widget:
            self.spectrum_widget.set_range(min_power, max_power)
            logger.info(f"Spectrum Y-axis range updated: {min_power} to {max_power} dB")
        
        if hasattr(self, 'waterfall_widget') and self.waterfall_widget:
            self.waterfall_widget.set_range(min_power, max_power)
            logger.info(f"Waterfall range updated: {min_power} to {max_power} dB")
    
    def _toggle_waterfall(self, state):
        """Переключение отображения waterfall"""
        if state:
            self.waterfall_widget.show()
        else:
            self.waterfall_widget.hide()
    
    def _toggle_trace_hold(self, state):
        """Переключение режима Trace Hold"""
        if hasattr(self, 'spectrum_widget'):
            self.spectrum_widget.set_trace_hold_enabled(bool(state))
    
    def _reset_trace_hold(self):
        """Сброс накопленных максимумов Trace Hold"""
        if hasattr(self, 'spectrum_widget'):
            self.spectrum_widget.reset_trace_hold()
    
    def _delete_selected_marker(self):
        """Удалить выбранный маркер"""
        if hasattr(self, 'spectrum_widget'):
            marker_id = self.spectrum_widget.get_selected_marker_id()
            if marker_id is not None:
                self.spectrum_widget.remove_marker(marker_id)
                self._update_marker_buttons()
    
    def _add_marker_dialog(self):
        """Диалог добавления маркера на заданной частоте"""
        from PySide6.QtWidgets import QInputDialog
        
        # Получаем текущий диапазон частот
        if hasattr(self, 'spectrum_widget'):
            # Вычисляем диапазон из центральной частоты и sample rate
            center_freq = self.spectrum_widget._center_freq / 1e6  # МГц
            sample_rate = self.spectrum_widget._sample_rate / 1e6  # МГц
            start_freq = center_freq - sample_rate / 2
            stop_freq = center_freq + sample_rate / 2
            
            # Диалог ввода частоты
            freq_mhz, ok = QInputDialog.getDouble(
                self,
                "Добавить маркер",
                f"Введите частоту маркера (МГц):\nДиапазон: {start_freq:.3f} - {stop_freq:.3f} МГц",
                center_freq,  # значение по умолчанию
                start_freq,   # минимум
                stop_freq,    # максимум
                3             # количество знаков после запятой
            )
            
            if ok:
                # Добавляем маркер
                # Мощность будет вычислена автоматически методом _get_power_at_frequency
                marker_id = self.spectrum_widget.add_marker(freq_mhz, 0.0, None)
                if marker_id is None:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(
                        self,
                        "Ошибка",
                        "Достигнут лимит маркеров (максимум 10)"
                    )
                else:
                    self._update_marker_buttons()
    
    def _clear_all_markers(self):
        """Очистить все маркеры"""
        if hasattr(self, 'spectrum_widget'):
            self.spectrum_widget.clear_all_markers()
            self._update_marker_buttons()
    
    def _update_marker_buttons(self):
        """Обновить состояние кнопок маркеров"""
        if hasattr(self, 'spectrum_widget'):
            markers = self.spectrum_widget.get_markers()
            has_markers = len(markers) > 0
            has_selection = self.spectrum_widget.get_selected_marker_id() is not None
            
            self.markers_clear_btn.setEnabled(has_markers)
            self.marker_delete_btn.setEnabled(has_selection)
    
    def _on_gain_changed(self, value: int):
        """Обработка изменения слайдера усиления"""
        gain_db = float(value)
        self.gain_value_label.setText(f"{gain_db:.0f} дБ")
        
        # Обновляем значение в gain_spin (синхронизация)
        self.gain_spin.blockSignals(True)
        self.gain_spin.setValue(int(gain_db))
        self.gain_spin.blockSignals(False)
        
        # Динамическое обновление усиления в работающем мониторе
        if self.monitor and self.monitor.state == MonitorState.RUNNING:
            self.monitor.set_gain(gain_db)
            logger.info(f"Gain changed to {gain_db:.0f} dB (dynamic update)")
        else:
            # Если монитор не запущен, просто обновляем конфиг
            self.config.device.gain = gain_db
    
    def _on_threshold_changed(self, value: int):
        """Обработка изменения слайдера порога"""
        threshold_db = float(value)
        self.threshold_value_label.setText(f"{threshold_db:.0f} дБ")
        
        # Сохраняем порог для текущего пресета
        if self._current_preset_name:
            self._preset_thresholds[self._current_preset_name] = threshold_db
        
        # Обновляем порог в активном диапазоне
        if self.config.ranges:
            for r in self.config.ranges:
                if r.enabled:
                    r.threshold_db = threshold_db
                    break
        
        # Динамическое обновление порога в работающем мониторе
        if self.monitor and self.monitor.state == MonitorState.RUNNING:
            self.monitor.set_threshold(threshold_db)
            logger.info(f"Threshold changed to {threshold_db:.0f} dB (dynamic update)")
        
        # Обновляем таблицу диапазонов
        self._update_ranges_table()
        
        # Обновляем отображение спектра
        if hasattr(self, 'spectrum_widget'):
            self.spectrum_widget.set_threshold(threshold_db)
    
    def _apply_ranges_to_monitor(self):
        """Применить изменения диапазонов - требует перезапуска мониторинга для RTL-SDR"""
        # RTL-SDR нестабилен при динамической смене частотных диапазонов
        # Поэтому нужен перезапуск мониторинга
        if self.monitor and self.monitor.state == MonitorState.RUNNING:
            enabled_ranges = [r for r in self.config.ranges if r.enabled]
            logger.info(f"Ranges changed: {len(enabled_ranges)} ranges - {[f'{r.name}: {r.start_freq/1e6:.1f}-{r.stop_freq/1e6:.1f} MHz' for r in enabled_ranges]}")
            
            # Перезапускаем мониторинг только если он был запущен
            if self.monitor and self.monitor.state == MonitorState.RUNNING:
                self.statusbar.showMessage("Перезапуск мониторинга для применения новых диапазонов...", 3000)
                self._stop_monitor()
                
                # Небольшая задержка для корректного закрытия устройства
                from PySide6.QtCore import QTimer
                QTimer.singleShot(100, self._start_monitor)
    
    def _test_telegram(self):
        """Тестирование подключения к Telegram"""
        token = self.telegram_token.text().strip()
        chat_id = self.telegram_chat_id.text().strip()
        
        if not token or not chat_id:
            QMessageBox.warning(self, "Telegram", "Введите Bot Token и Chat ID")
            return
        
        # Создаём временный конфиг
        test_config = TelegramConfig(
            enabled=True,
            bot_token=token,
            chat_id=chat_id,
        )
        
        notifier = TelegramNotifier(test_config)
        success, message = notifier.test_connection()
        
        if success:
            # Отправляем тестовое сообщение
            notifier.start()
            notifier.notify_status("✅ Test successful!\n\nRF Event Analyzer Pro connected.")
            import time
            time.sleep(1)
            notifier.stop()
            QMessageBox.information(self, "Telegram", f"Подключение успешно!\n{message}")
        else:
            QMessageBox.critical(self, "Telegram", f"Ошибка подключения:\n{message}")
    
    def _apply_telegram_settings_dynamic(self):
        """Динамическое применение Telegram настроек без перезапуска мониторинга"""
        # Сохраняем настройки
        self._save_telegram_settings()
        
        # Если мониторинг запущен, обновляем настройки
        if hasattr(self, 'monitor') and self.monitor and self.monitor.state == MonitorState.RUNNING:
            # Обновляем конфиг Telegram
            if self.telegram_enabled.isChecked():
                new_config = TelegramConfig(
                    enabled=True,
                    bot_token=self.telegram_token.text().strip(),
                    chat_id=self.telegram_chat_id.text().strip(),
                    min_power_db=self.telegram_min_power.value(),
                    cooldown_seconds=self.telegram_cooldown.currentData(),
                )
                
                # Перезапускаем Telegram notifier с новыми настройками
                if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
                    self.telegram_notifier.stop()
                
                self.telegram_config = new_config
                self.telegram_notifier = TelegramNotifier(self.telegram_config)
                if self.telegram_notifier.start():
                    logger.info(f"Telegram settings updated dynamically: min_power={new_config.min_power_db} dB, "
                               f"cooldown={new_config.cooldown_seconds}s")
            else:
                # Выключаем Telegram
                if hasattr(self, 'telegram_notifier') and self.telegram_notifier:
                    self.telegram_notifier.stop()
                    self.telegram_notifier = None
                    logger.info("Telegram notifications disabled dynamically")
    
    def _switch_to_preset(self, name: str, start_mhz: float, stop_mhz: float):
        """Быстрое переключение на предустановленный диапазон"""
        if not self.monitor or self.monitor.state != MonitorState.RUNNING:
            return
        
        logger.info(f"Switching to preset: {name} ({start_mhz}-{stop_mhz} MHz)")
        
        # Восстанавливаем сохраненный порог для этого пресета или используем текущий
        threshold_db = self._preset_thresholds.get(name, self.threshold_slider.value())
        
        # Обновляем слайдер порога
        self.threshold_slider.setValue(int(threshold_db))
        self.threshold_value_label.setText(f"{threshold_db:.0f} дБ")
        
        # Запоминаем текущий пресет
        self._current_preset_name = name
        
        # Создаём временный диапазон
        from rf_analyzer.core.config import FrequencyRange
        temp_range = FrequencyRange(
            name=name,
            start_freq=start_mhz * 1e6,
            stop_freq=stop_mhz * 1e6,
            threshold_db=threshold_db,
            min_duration_ms=100.0,
            enabled=True
        )
        
        # Обновляем конфигурацию монитора
        self.config.ranges = [temp_range]
        
        # Перезапускаем мониторинг с новым диапазоном
        self.statusbar.showMessage(f"Переключение на {name}...", 2000)
        self._stop_monitor()
        
        # Небольшая задержка для корректного закрытия устройства
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self._start_monitor)
    
    def _start_monitor(self):
        # Программа теперь бесплатная - нет проверки лицензии
        if not self.config.ranges:
            QMessageBox.warning(self, "Настройки", "Добавьте хотя бы один диапазон")
            return
        
        # Применяем настройки устройства
        device_map = {
            0: DeviceType.RTLSDR,
            1: DeviceType.HACKRF,
            2: DeviceType.LIBRESDR,
            3: DeviceType.USRP,
        }
        self.config.device.device_type = device_map[self.device_combo.currentIndex()]
        
        sample_rates = [1.0e6, 2.0e6, 2.4e6, 3.2e6]
        self.config.device.sample_rate = sample_rates[self.sample_rate.currentIndex()]
        self.config.device.gain = self.gain_spin.value()
        
        # Применяем настройки детекции
        self.config.detection.impulse_threshold_db = self.impulse_threshold.value()
        self.config.detection.noise_floor_averaging = self.noise_avg_spin.value()
        self.config.detection.fft_size = [256, 512, 1024, 2048, 4096][self.fft_size.currentIndex()]
        
        # Создаём хранилище
        self.storage = EventStorage(self.config.output.database_path)
        
        # Создаём монитор
        self.monitor = RFMonitor(
            self.config,
            self.storage,
            on_event=self._on_event,
            on_event_started=self._on_event_started,
        )
        
        try:
            is_started = self.monitor.start()
        except Exception as e:
            logger.error(f"Monitor start exception: {e}")
            is_started = False

        if is_started:
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            for btn in self.preset_buttons.values():
                btn.setEnabled(True)
            self.status_indicator.set_status("Работает", "#34d399")
            self.statusbar.showMessage("Мониторинг запущен", 3000)
            
            # Обновляем слайдер порога из активного диапазона
            if self.config.ranges:
                for r in self.config.ranges:
                    if r.enabled:
                        self.threshold_slider.setValue(int(r.threshold_db))
                        self.threshold_value_label.setText(f"{r.threshold_db:.0f} дБ")
                        break
            
            # Запускаем Telegram уведомления если настроены
            if self.telegram_enabled.isChecked():
                self.telegram_config = TelegramConfig(
                    enabled=True,
                    bot_token=self.telegram_token.text().strip(),
                    chat_id=self.telegram_chat_id.text().strip(),
                    min_power_db=self.telegram_min_power.value(),
                    cooldown_seconds=self.telegram_cooldown.currentData(),
                )
                self.telegram_notifier = TelegramNotifier(self.telegram_config)
                if self.telegram_notifier.start():
                    logger.info(f"Telegram notifier started: min_power={self.telegram_config.min_power_db} dB, "
                               f"cooldown={self.telegram_config.cooldown_seconds}s")
                else:
                    logger.warning("Failed to start Telegram notifier")
        else:
            error_msg = "Не удалось запустить мониторинг.\n\n"
            device_type = self.device_combo.currentText()
            
            if device_type == "RTL-SDR":
                error_msg += "Проверьте:\n"
                error_msg += "- Подключено ли устройство RTL-SDR\n"
                error_msg += "- Установлен ли драйвер Zadig (WinUSB)\n"
                error_msg += "- Не используется ли устройство другой программой"
            elif device_type == "USRP (B200/B210)":
                error_msg += "Проверьте:\n"
                error_msg += "- Подключено ли устройство USRP по USB\n"
                error_msg += "- Установлен ли UHD Python API\n"
                error_msg += "  (pip install uhd - не работает на Windows)\n"
                error_msg += "- Для Windows: используйте GNU Radio или\n"
                error_msg += "  скомпилируйте UHD с Python bindings\n"
                error_msg += "- Файлы прошивки в ~/.uhd/images/\n"
                error_msg += "- Смотрите подробности в логах консоли"
                error_msg += "Проверьте:\n"
                error_msg += "- Подключено ли устройство LibreSDR по USB\n"
                error_msg += "- Или доступно ли по сети 192.168.2.1\n"
                error_msg += "- Установлены ли драйверы libiio\n"
                error_msg += "- Смотрите подробности в логах консоли"
            elif device_type == "HackRF":
                error_msg += "Проверьте:\n"
                error_msg += "- Подключено ли устройство HackRF\n"
                error_msg += "- Установлены ли драйверы"

            # Показываем реальную причину (если доступна)
            try:
                if getattr(self.monitor, "last_start_error_message", None):
                    error_msg += f"\n\nПричина: {self.monitor.last_start_error_message}"
            except Exception:
                pass
            QMessageBox.critical(self, "Ошибка", error_msg)
    
    def _stop_monitor(self):
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        
        # Останавливаем Telegram
        if self.telegram_notifier:
            self.telegram_notifier.stop()
            self.telegram_notifier = None
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        for btn in self.preset_buttons.values():
            btn.setEnabled(False)
        self.status_indicator.set_status("Остановлен", "#71717a")
        self.status_indicator.set_uptime("")  # Очищаем время
        self.statusbar.showMessage("Мониторинг остановлен", 3000)
    
    def _on_event(self, event: RFEvent):
        """Callback для завершённого события (приходит из потока монитора)."""
        self.event_completed.emit(event)

    @Slot(object)
    def _on_event_ui(self, event: RFEvent) -> None:
        """UI-обработчик завершённого события."""
        self._upsert_event_row(event, completed=True)

    def _on_event_started(self, event: RFEvent):
        """Callback для активного события (достигло min_duration) — приходит из потока монитора."""
        self.event_active.emit(event)

    @Slot(object)
    def _on_event_active_ui(self, event: RFEvent) -> None:
        """UI-обработчик активного события: показываем в таблице и отправляем Telegram."""
        # Показываем (без сохранения в БД — это активное событие)
        self._upsert_event_row(event, completed=False)

        # Telegram
        if self.telegram_notifier:
            self.telegram_notifier.notify_event(event)
    
    def _update_stats(self):
        if self.monitor and self.monitor.state == MonitorState.RUNNING:
            stats = self.monitor.get_stats()
            
            # Watchdog: проверяем что монитор не завис (нет активности > 30 сек)
            if hasattr(self.monitor, '_last_activity_time'):
                import time
                inactivity = time.time() - self.monitor._last_activity_time
                if inactivity > 30:
                    logger.warning(f"Monitor watchdog: {inactivity:.1f}s inactivity, attempting restart")
                    self._stop_monitoring()
                    time.sleep(1)
                    self._start_monitoring()
                    return
            
            # Обновляем статистику всегда (независимо от FPS лимита)
            # Форматируем время и отображаем в статусе
            mins, secs = divmod(int(stats.uptime_seconds), 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                uptime_text = f"{hours}:{mins:02d}:{secs:02d}"
            else:
                uptime_text = f"{mins}:{secs:02d}"
            self.status_indicator.set_uptime(uptime_text)
            
            self.current_range_label.setText(f"{stats.current_range} | Событий: {stats.events_detected}")
            
            # Обновляем спектр и waterfall (с ограничением FPS для экономии CPU)
            import time
            current_time = time.time()
            if current_time - self._last_gui_update < self._min_update_interval:
                return  # Пропускаем обновление графиков, но статистика уже обновлена
            
            self._last_gui_update = current_time
            
            if hasattr(self.monitor, '_processor') and self.monitor._processor:
                processor = self.monitor._processor
                if hasattr(processor, 'last_spectrum') and processor.last_spectrum is not None:
                    spectrum = processor.last_spectrum
                    
                    # Проверяем что это новый спектр (по timestamp)
                    if spectrum.timestamp > self._last_spectrum_timestamp:
                        self._last_spectrum_timestamp = spectrum.timestamp
                        
                        center_freq = stats.current_freq_mhz * 1e6 if stats.current_freq_mhz else 100e6
                        sample_rate = self.config.device.sample_rate
                        
                        # Проверяем что power_db валиден
                        if spectrum.power_db is not None and len(spectrum.power_db) > 0:
                            # Получаем threshold из текущего диапазона
                            threshold = -60.0  # дефолт
                            if self.config.ranges:
                                for r in self.config.ranges:
                                    if r.enabled:
                                        threshold = r.threshold_db
                                        break
                            
                            # Обновляем виджет спектра
                            self.spectrum_widget.set_spectrum(
                                spectrum.power_db,
                                center_freq=center_freq,
                                sample_rate=sample_rate
                            )
                            self.spectrum_widget.set_threshold(threshold)
                            
                            # Добавляем в waterfall (только если включен)
                            if self.waterfall_enabled.isChecked():
                                self.waterfall_widget.add_spectrum(
                                    spectrum.power_db,
                                    center_freq=center_freq,
                                    sample_rate=sample_rate
                                )
        
        # Обновляем статистику в табе отчётов
        if self.storage:
            try:
                days = self.report_days.value()
                hours = self.report_hours.value()
                minutes = self.report_minutes.value()
                
                # Формируем текстовое описание периода
                period_parts = []
                if days > 0:
                    period_parts.append(f"{days} дн.")
                if hours > 0:
                    period_parts.append(f"{hours} ч.")
                if minutes > 0:
                    period_parts.append(f"{minutes} мин.")
                
                period_text = " ".join(period_parts) if period_parts else "не указан"
                
                # Вычисляем начальную дату
                total_timedelta = timedelta(days=days, hours=hours, minutes=minutes)
                start = datetime.now() - total_timedelta if total_timedelta.total_seconds() > 0 else datetime.now()
                stats = self.storage.get_statistics(start_time=start)
                
                text = f"<b>Статистика за последние {period_text}</b><br><br>"
                text += f"Всего событий: <b style='color: #60a5fa;'>{stats['total_events']}</b><br>"
                text += f"Макс. уровень: <b style='color: #f87171;'>{stats['max_power_db']:.1f} дБ</b><br>"
                text += f"Ср. длительность: <b style='color: #34d399;'>{stats['avg_duration_ms']:.0f} мс</b><br><br>"
                
                if stats['by_type']:
                    text += "<b>По типам:</b><br>"
                    for t, c in stats['by_type'].items():
                        text += f"  • {t}: {c}<br>"
                
                self.stats_text.setHtml(text)
            except Exception:
                pass
    
    def _generate_report(self):
        # Программа теперь бесплатная - нет ограничений
        if not self.storage:
            self.storage = EventStorage(self.config.output.database_path)
        
        # Вычисляем период с учётом дней, часов и минут
        days = self.report_days.value()
        hours = self.report_hours.value()
        minutes = self.report_minutes.value()
        
        # Проверяем что задан хотя бы один параметр времени
        if days == 0 and hours == 0 and minutes == 0:
            QMessageBox.warning(
                self, "Некорректный период",
                "Укажите хотя бы один параметр времени (дни, часы или минуты)."
            )
            return
        
        total_timedelta = timedelta(days=days, hours=hours, minutes=minutes)
        start_time = datetime.now() - total_timedelta
        end_time = datetime.now()
        
        format_map = {0: "pdf", 1: "html", 2: "csv"}
        fmt = format_map[self.report_format.currentIndex()]
        
        # Выбор файла
        filters = {
            "pdf": "PDF Files (*.pdf)",
            "html": "HTML Files (*.html)",
            "csv": "CSV Files (*.csv)",
        }
        
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт",
            f"report_{datetime.now().strftime('%Y%m%d')}.{fmt}",
            filters[fmt]
        )
        
        if not path:
            return
        
        try:
            generator = ReportGenerator(self.storage)
            output_path = Path(path)
            
            if fmt == "pdf":
                generator.generate_pdf_report(
                    start_time, end_time, output_path,
                    self.report_title.text()
                )
            elif fmt == "html":
                generator.save_html_report(
                    start_time, end_time, output_path,
                    self.report_title.text()
                )
            else:
                generator.generate_csv_report(start_time, end_time, output_path)
            
            self.license_mgr.record_report_generated()
            
            QMessageBox.information(
                self, "Успех",
                f"Отчёт успешно сохранён:\n{output_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка генерации: {e}")
    
    def _on_report_period_changed(self):
        """Обработчик изменения параметров периода отчёта - обновляет статистику"""
        # Принудительно обновляем статистику
        if self.storage:
            try:
                days = self.report_days.value()
                hours = self.report_hours.value()
                minutes = self.report_minutes.value()
                
                # Формируем текстовое описание периода
                period_parts = []
                if days > 0:
                    period_parts.append(f"{days} дн.")
                if hours > 0:
                    period_parts.append(f"{hours} ч.")
                if minutes > 0:
                    period_parts.append(f"{minutes} мин.")
                
                period_text = " ".join(period_parts) if period_parts else "не указан"
                
                # Вычисляем начальную дату
                total_timedelta = timedelta(days=days, hours=hours, minutes=minutes)
                start = datetime.now() - total_timedelta if total_timedelta.total_seconds() > 0 else datetime.now()
                stats = self.storage.get_statistics(start_time=start)
                
                text = f"<b>Статистика за последние {period_text}</b><br><br>"
                text += f"Всего событий: <b style='color: #60a5fa;'>{stats['total_events']}</b><br>"
                text += f"Макс. уровень: <b style='color: #f87171;'>{stats['max_power_db']:.1f} дБ</b><br>"
                text += f"Ср. длительность: <b style='color: #34d399;'>{stats['avg_duration_ms']:.0f} мс</b><br><br>"
                
                if stats['by_type']:
                    text += "<b>По типам:</b><br>"
                    for t, c in stats['by_type'].items():
                        text += f"  • {t}: {c}<br>"
                
                self.stats_text.setHtml(text)
            except Exception as e:
                logger.debug(f"Failed to update report statistics: {e}")
    
    def _set_report_period(self, days: int, hours: int, minutes: int):
        """Установить период отчёта"""
        self.report_days.setValue(days)
        self.report_hours.setValue(hours)
        self.report_minutes.setValue(minutes)
    
    def _show_license_dialog(self):
        dialog = LicenseDialog(self.license_mgr, self)
        dialog.exec()
        self._update_license_status()
    
    def _show_about(self):
        QMessageBox.about(
            self, "О программе",
            "<h2>RF Event Analyzer Pro</h2>"
            "<p><b>Версия 1.0.0</b></p>"
            "<hr>"
            "<p>Профессиональный инструмент для автоматического "
            "мониторинга и анализа RF-событий.</p>"
            "<br>"
            "<p><b>Возможности:</b></p>"
            "<ul>"
            "<li>Автоматическая детекция RF-событий</li>"
            "<li>Поддержка RTL-SDR и HackRF</li>"
            "<li>Генерация PDF/HTML отчётов</li>"
            "<li>Экспорт данных в CSV</li>"
            "<li>Детекция импульсов и аномалий</li>"
            "</ul>"
            "<hr>"
            "<p style='color: #a1a1aa;'>© 2024 RF Solutions</p>"
        )
    
    def closeEvent(self, event):
        # Сохраняем настройки перед выходом
        self._save_settings()
        
        if self.monitor and self.monitor.state == MonitorState.RUNNING:
            reply = QMessageBox.question(
                self, "Выход",
                "Мониторинг активен. Остановить и выйти?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self._stop_monitor()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
    
    def _load_settings(self) -> AppConfig:
        """Загрузить настройки из файла"""
        try:
            # Check local config.yaml first
            local_config = Path.cwd() / "config.yaml"
            if local_config.exists():
                logger.info(f"Loading settings from local file: {local_config}")
                return AppConfig.load(local_config)

            if SETTINGS_FILE.exists():
                logger.info(f"Loading settings from {SETTINGS_FILE}")
                return AppConfig.load(SETTINGS_FILE)
            else:
                logger.info("No saved settings found, using defaults")
                return AppConfig.default()
        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            return AppConfig.default()
    
    def _load_telegram_settings(self) -> TelegramConfig:
        """Загрузить настройки Telegram из файла"""
        try:
            telegram_file = SETTINGS_FILE.parent / "telegram.yaml"
            if telegram_file.exists():
                import yaml
                with open(telegram_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                return TelegramConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load Telegram settings: {e}")
        return TelegramConfig()
    
    def _save_settings(self):
        """Сохранить все настройки в файл"""
        try:
            # Создаём директорию если не существует
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Собираем текущие настройки из UI
            self._collect_settings_from_ui()
            
            # Сохраняем основные настройки
            self.config.save(SETTINGS_FILE)
            logger.info(f"Settings saved to {SETTINGS_FILE}")
            
            # Сохраняем UI состояния (waterfall, trace hold)
            self._save_ui_state()
            
            # Сохраняем настройки Telegram отдельно (содержат токен)
            self._save_telegram_settings()
            
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
    
    def _save_telegram_settings(self):
        """Сохранить настройки Telegram"""
        try:
            import yaml
            telegram_file = SETTINGS_FILE.parent / "telegram.yaml"
            
            telegram_data = {
                "enabled": self.telegram_enabled.isChecked(),
                "bot_token": self.telegram_token.text().strip(),
                "chat_id": self.telegram_chat_id.text().strip(),
                "min_power_db": self.telegram_min_power.value(),
                "notify_on_event": True,
                "notify_on_error": True,
                "cooldown_seconds": self.telegram_cooldown.currentData(),
            }
            
            with open(telegram_file, "w", encoding="utf-8") as f:
                yaml.dump(telegram_data, f, default_flow_style=False, allow_unicode=True)
            
            logger.info(f"Telegram settings saved")
        except Exception as e:
            logger.error(f"Failed to save Telegram settings: {e}")
    
    def _save_ui_state(self):
        """Сохранить состояние UI элементов"""
        try:
            import yaml
            import numpy as np
            ui_state_file = SETTINGS_FILE.parent / "ui_state.yaml"
            
            # Получаем маркеры из виджета спектра
            markers = {}
            if hasattr(self, 'spectrum_widget'):
                raw_markers = self.spectrum_widget.get_markers()
                # Конвертируем numpy типы в Python типы
                for marker_id, marker_data in raw_markers.items():
                    markers[marker_id] = {
                        'freq_mhz': float(marker_data['freq_mhz']),
                        'power_main_db': float(marker_data['power_main_db']),
                        'power_trace_db': float(marker_data['power_trace_db']) if marker_data.get('power_trace_db') is not None else None
                    }
            
            ui_state = {
                "waterfall_enabled": self.waterfall_enabled.isChecked(),
                "trace_hold_enabled": self.trace_hold_enabled.isChecked(),
                "threshold_db": self.threshold_slider.value(),
                "fft_size_index": self.fft_size.currentIndex(),
                "preset_thresholds": self._preset_thresholds,
                "current_preset_name": self._current_preset_name,
                "markers": markers,
            }
            
            with open(ui_state_file, "w", encoding="utf-8") as f:
                yaml.dump(ui_state, f, default_flow_style=False, allow_unicode=True)
            
            logger.info("UI state saved")
        except Exception as e:
            logger.error(f"Failed to save UI state: {e}")
    
    def _load_ui_state(self):
        """Загрузить состояние UI элементов"""
        try:
            import yaml
            ui_state_file = SETTINGS_FILE.parent / "ui_state.yaml"
            
            if ui_state_file.exists():
                with open(ui_state_file, "r", encoding="utf-8") as f:
                    ui_state = yaml.safe_load(f) or {}
                
                # Применяем сохраненные состояния
                if "waterfall_enabled" in ui_state:
                    self.waterfall_enabled.setChecked(ui_state["waterfall_enabled"])
                
                if "trace_hold_enabled" in ui_state:
                    self.trace_hold_enabled.setChecked(ui_state["trace_hold_enabled"])
                    if hasattr(self, 'spectrum_widget'):
                        self.spectrum_widget.set_trace_hold_enabled(ui_state["trace_hold_enabled"])
                
                # Загружаем значение порога
                if "threshold_db" in ui_state:
                    threshold_value = int(ui_state["threshold_db"])
                    self.threshold_slider.setValue(threshold_value)
                    self.threshold_value_label.setText(f"{threshold_value} дБ")
                
                # Загружаем FFT размер
                if "fft_size_index" in ui_state:
                    fft_index = int(ui_state["fft_size_index"])
                    if 0 <= fft_index < self.fft_size.count():
                        self.fft_size.setCurrentIndex(fft_index)
                
                # Загружаем пороги пресетов
                if "preset_thresholds" in ui_state:
                    self._preset_thresholds = ui_state["preset_thresholds"] or {}
                
                if "current_preset_name" in ui_state:
                    self._current_preset_name = ui_state["current_preset_name"]
                
                # Загружаем маркеры
                if "markers" in ui_state and hasattr(self, 'spectrum_widget'):
                    markers = ui_state["markers"]
                    if isinstance(markers, dict):
                        # Конвертируем ключи обратно в int (YAML сохраняет как строки)
                        markers_int = {int(k): v for k, v in markers.items()}
                        self.spectrum_widget.set_markers(markers_int)
                
                logger.info("UI state loaded")
        except Exception as e:
            logger.error(f"Failed to load UI state: {e}")
    
    def _collect_settings_from_ui(self):
        """Собрать текущие настройки из UI элементов"""
        # Настройки устройства
        device_map = {
            0: DeviceType.RTLSDR,
            1: DeviceType.HACKRF,
            2: DeviceType.LIBRESDR,
            3: DeviceType.USRP,
        }
        self.config.device.device_type = device_map.get(self.device_combo.currentIndex(), DeviceType.USRP)
        
        sample_rates = [1.0e6, 2.0e6, 2.4e6, 3.2e6]
        self.config.device.sample_rate = sample_rates[self.sample_rate.currentIndex()]
        self.config.device.gain = self.gain_spin.value()
        
        # Настройки детекции
        self.config.detection.impulse_threshold_db = self.impulse_threshold.value()
        self.config.detection.noise_floor_averaging = self.noise_avg_spin.value()
        
        fft_sizes = [256, 512, 1024, 2048, 4096]
        self.config.detection.fft_size = fft_sizes[self.fft_size.currentIndex()]
    
    def _apply_loaded_settings_to_ui(self):
        """Применить загруженные настройки к UI элементам"""
        try:
            # Блокируем сигналы чтобы не запускался мониторинг
            widgets_to_block = [
                self.device_combo, self.sample_rate, self.gain_spin,
                self.impulse_threshold, self.noise_avg_spin, self.fft_size
            ]
            for widget in widgets_to_block:
                widget.blockSignals(True)
            
            try:
                # Устройство
                device_index = {
                    DeviceType.RTLSDR: 0,
                    DeviceType.HACKRF: 1,
                    DeviceType.LIBRESDR: 2,
                    DeviceType.USRP: 3,
                }.get(self.config.device.device_type, 3)  # По умолчанию USRP
                self.device_combo.setCurrentIndex(device_index)
                
                # Sample rate
                sample_rates = [1.0e6, 2.0e6, 2.4e6, 3.2e6]
                try:
                    sr_index = sample_rates.index(self.config.device.sample_rate)
                except ValueError:
                    sr_index = 1  # 2.0 MHz по умолчанию
                self.sample_rate.setCurrentIndex(sr_index)
                
                # Gain
                self.gain_spin.setValue(self.config.device.gain)
                
                # Детекция
                self.impulse_threshold.setValue(self.config.detection.impulse_threshold_db)
                self.noise_avg_spin.setValue(self.config.detection.noise_floor_averaging)
                
                # FFT size
                fft_sizes = [256, 512, 1024, 2048, 4096]
                try:
                    fft_index = fft_sizes.index(self.config.detection.fft_size)
                except ValueError:
                    fft_index = 2  # 1024 по умолчанию
                self.fft_size.setCurrentIndex(fft_index)
                
            finally:
                # Разблокируем сигналы
                for widget in widgets_to_block:
                    widget.blockSignals(False)
            
            # Диапазоны (не применяем к монитору при загрузке)
            self._update_ranges_table(apply_to_monitor=False)
            
            # Telegram настройки - блокируем сигналы чтобы не перезаписать сохранённые значения
            self.telegram_enabled.blockSignals(True)
            self.telegram_token.blockSignals(True)
            self.telegram_chat_id.blockSignals(True)
            self.telegram_min_power.blockSignals(True)
            self.telegram_cooldown.blockSignals(True)
            
            logger.info(f"Loading Telegram settings: enabled={self.telegram_config.enabled}, "
                       f"bot_token={'***' if self.telegram_config.bot_token else 'empty'}, "
                       f"chat_id={self.telegram_config.chat_id}, "
                       f"min_power={self.telegram_config.min_power_db}, "
                       f"cooldown={self.telegram_config.cooldown_seconds}")
            
            self.telegram_enabled.setChecked(self.telegram_config.enabled)
            self.telegram_token.setText(self.telegram_config.bot_token)
            self.telegram_chat_id.setText(self.telegram_config.chat_id)
            self.telegram_min_power.setValue(self.telegram_config.min_power_db)
            
            # Загружаем cooldown в комбобокс
            cooldown = self.telegram_config.cooldown_seconds
            for i in range(self.telegram_cooldown.count()):
                if self.telegram_cooldown.itemData(i) == cooldown:
                    self.telegram_cooldown.setCurrentIndex(i)
                    break
            
            # Разблокируем сигналы
            self.telegram_enabled.blockSignals(False)
            self.telegram_token.blockSignals(False)
            self.telegram_chat_id.blockSignals(False)
            self.telegram_min_power.blockSignals(False)
            self.telegram_cooldown.blockSignals(False)
            
            logger.info("UI updated with loaded settings")
            
        except Exception as e:
            logger.error(f"Failed to apply settings to UI: {e}")


def run_gui():
    """Точка входа для GUI"""
    # Настраиваем логирование в файл с ротацией
    from rf_analyzer.utils.logging_config import setup_logging
    setup_logging(
        log_file="logs/rf_analyzer.log",
        log_level="INFO",
        max_bytes=10485760,  # 10MB
        backup_count=5
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("RF Event Analyzer Pro starting...")
    logger.info("=" * 60)
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Устанавливаем тёмную палитру
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 46))
    palette.setColor(QPalette.WindowText, QColor(228, 228, 231))
    palette.setColor(QPalette.Base, QColor(30, 30, 46))
    palette.setColor(QPalette.AlternateBase, QColor(45, 45, 61))
    palette.setColor(QPalette.Text, QColor(228, 228, 231))
    palette.setColor(QPalette.Button, QColor(61, 61, 79))
    palette.setColor(QPalette.ButtonText, QColor(228, 228, 231))
    palette.setColor(QPalette.Highlight, QColor(26, 115, 232))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.Link, QColor(96, 165, 250))
    app.setPalette(palette)
    
    window = MainWindow()
    window.show()
    
    logger.info("Main window displayed")
    
    try:
        exit_code = app.exec()
        logger.info(f"Application exited with code {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Application crashed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_gui()
