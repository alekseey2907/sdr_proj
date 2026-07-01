"""
RF Event Analyzer - Spectrum Widgets
Виджеты для отображения спектра и водопада
"""
from __future__ import annotations

import numpy as np
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QRectF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QPainterPath


class SpectrumWidget(QWidget):
    """Виджет отображения спектра в реальном времени"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Данные спектра
        self.spectrum_data: Optional[np.ndarray] = None
        self.freq_start = 100e6  # Гц
        self.freq_stop = 110e6  # Гц
        self.threshold_db = -60
        self.noise_floor_db = -90
        
        # Цвета
        self.bg_color = QColor(30, 30, 46)
        self.grid_color = QColor(61, 61, 79)
        self.spectrum_color = QColor(96, 165, 250)
        self.threshold_color = QColor(248, 113, 113)
        self.fill_color = QColor(96, 165, 250, 50)
        self.text_color = QColor(161, 161, 170)
        
        # Параметры отображения
        self.db_min = -80
        self.db_max = 60
        self.margin_left = 50
        self.margin_right = 20
        self.margin_top = 20
        self.margin_bottom = 40
    
    def set_spectrum(self, spectrum: np.ndarray, freq_start: float, freq_stop: float):
        """Установить новые данные спектра"""
        self.spectrum_data = spectrum
        self.freq_start = freq_start
        self.freq_stop = freq_stop
        self.update()
    
    def set_threshold(self, threshold_db: float):
        """Установить порог срабатывания"""
        self.threshold_db = threshold_db
        self.update()
    
    def set_noise_floor(self, noise_floor_db: float):
        """Установить уровень шума"""
        self.noise_floor_db = noise_floor_db
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        
        # Фон
        painter.fillRect(0, 0, width, height, self.bg_color)
        
        # Область графика
        plot_x = self.margin_left
        plot_y = self.margin_top
        plot_width = width - self.margin_left - self.margin_right
        plot_height = height - self.margin_top - self.margin_bottom
        
        # Сетка
        painter.setPen(QPen(self.grid_color, 1, Qt.DotLine))
        
        # Горизонтальные линии (дБ)
        for i in range(5):
            y = plot_y + i * plot_height / 4
            painter.drawLine(int(plot_x), int(y), int(plot_x + plot_width), int(y))
            
            db_val = self.db_max - i * (self.db_max - self.db_min) / 4
            painter.setPen(self.text_color)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(5, int(y + 4), f"{db_val:.0f}")
            painter.setPen(QPen(self.grid_color, 1, Qt.DotLine))
        
        # Вертикальные линии (частота)
        for i in range(5):
            x = plot_x + i * plot_width / 4
            painter.drawLine(int(x), int(plot_y), int(x), int(plot_y + plot_height))
            
            freq_val = self.freq_start + i * (self.freq_stop - self.freq_start) / 4
            painter.setPen(self.text_color)
            painter.drawText(int(x - 25), int(height - 10), f"{freq_val/1e6:.1f}")
            painter.setPen(QPen(self.grid_color, 1, Qt.DotLine))
        
        # Подписи осей
        painter.setPen(self.text_color)
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(int(width/2 - 30), int(height - 2), "Частота (МГц)")
        
        painter.save()
        painter.translate(12, int(height/2 + 20))
        painter.rotate(-90)
        painter.drawText(0, 0, "Уровень (дБ)")
        painter.restore()
        
        # Порог срабатывания
        if self.db_min <= self.threshold_db <= self.db_max:
            y = plot_y + plot_height * (self.db_max - self.threshold_db) / (self.db_max - self.db_min)
            painter.setPen(QPen(self.threshold_color, 2, Qt.DashLine))
            painter.drawLine(int(plot_x), int(y), int(plot_x + plot_width), int(y))
            
            painter.setPen(self.threshold_color)
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(int(plot_x + plot_width - 60), int(y - 5), f"Порог {self.threshold_db:.0f}")
        
        # Спектр
        if self.spectrum_data is not None and len(self.spectrum_data) > 0:
            path = QPainterPath()
            fill_path = QPainterPath()
            
            n_points = len(self.spectrum_data)
            
            for i, power in enumerate(self.spectrum_data):
                x = plot_x + i * plot_width / (n_points - 1)
                
                # Ограничиваем значения
                power_clamped = max(self.db_min, min(self.db_max, power))
                y = plot_y + plot_height * (self.db_max - power_clamped) / (self.db_max - self.db_min)
                
                if i == 0:
                    path.moveTo(x, y)
                    fill_path.moveTo(x, plot_y + plot_height)
                    fill_path.lineTo(x, y)
                else:
                    path.lineTo(x, y)
                    fill_path.lineTo(x, y)
            
            # Заливка под графиком
            fill_path.lineTo(plot_x + plot_width, plot_y + plot_height)
            fill_path.closeSubpath()
            
            gradient = QLinearGradient(0, plot_y, 0, plot_y + plot_height)
            gradient.setColorAt(0, QColor(96, 165, 250, 100))
            gradient.setColorAt(1, QColor(96, 165, 250, 10))
            painter.fillPath(fill_path, QBrush(gradient))
            
            # Линия спектра
            painter.setPen(QPen(self.spectrum_color, 2))
            painter.drawPath(path)
        
        # Рамка области графика
        painter.setPen(QPen(self.grid_color, 1))
        painter.drawRect(int(plot_x), int(plot_y), int(plot_width), int(plot_height))


class WaterfallWidget(QWidget):
    """Виджет водопада (история спектра)"""
    
    def __init__(self, history_size: int = 100, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.history_size = history_size
        self.history: deque = deque(maxlen=history_size)
        
        self.freq_start = 100e6
        self.freq_stop = 110e6
        
        self.db_min = -80
        self.db_max = 20
        
        self.margin_left = 50
        self.margin_right = 20
        self.margin_top = 10
        self.margin_bottom = 30
        
        # Цветовая схема (синий -> жёлтый -> красный)
        self.colors = self._generate_colormap()
    
    def _generate_colormap(self) -> list:
        """Генерация цветовой карты"""
        colors = []
        for i in range(256):
            if i < 85:
                # Синий -> Голубой
                r = 0
                g = int(i * 255 / 85)
                b = 255
            elif i < 170:
                # Голубой -> Жёлтый
                r = int((i - 85) * 255 / 85)
                g = 255
                b = 255 - int((i - 85) * 255 / 85)
            else:
                # Жёлтый -> Красный
                r = 255
                g = 255 - int((i - 170) * 255 / 85)
                b = 0
            colors.append(QColor(r, g, b))
        return colors
    
    def add_spectrum(self, spectrum: np.ndarray):
        """Добавить линию спектра"""
        self.history.append(spectrum.copy())
        self.update()
    
    def set_freq_range(self, freq_start: float, freq_stop: float):
        """Установить диапазон частот"""
        self.freq_start = freq_start
        self.freq_stop = freq_stop
        self.update()
    
    def clear(self):
        """Очистить историю"""
        self.history.clear()
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        
        width = self.width()
        height = self.height()
        
        # Фон
        painter.fillRect(0, 0, width, height, QColor(30, 30, 46))
        
        # Область графика
        plot_x = self.margin_left
        plot_y = self.margin_top
        plot_width = width - self.margin_left - self.margin_right
        plot_height = height - self.margin_top - self.margin_bottom
        
        if len(self.history) > 0 and plot_width > 0 and plot_height > 0:
            row_height = max(1, plot_height / len(self.history))
            
            for row_idx, spectrum in enumerate(self.history):
                y = plot_y + row_idx * row_height
                n_points = len(spectrum)
                col_width = max(1, plot_width / n_points)
                
                for col_idx, power in enumerate(spectrum):
                    x = plot_x + col_idx * col_width
                    
                    # Нормализация значения
                    normalized = (power - self.db_min) / (self.db_max - self.db_min)
                    normalized = max(0, min(1, normalized))
                    
                    color_idx = int(normalized * 255)
                    color = self.colors[color_idx]
                    
                    painter.fillRect(int(x), int(y), max(1, int(col_width) + 1), max(1, int(row_height) + 1), color)
        
        # Рамка
        painter.setPen(QPen(QColor(61, 61, 79), 1))
        painter.drawRect(int(plot_x), int(plot_y), int(plot_width), int(plot_height))
        
        # Подписи частот
        painter.setPen(QColor(161, 161, 170))
        painter.setFont(QFont("Segoe UI", 9))
        
        for i in range(5):
            x = plot_x + i * plot_width / 4
            freq_val = self.freq_start + i * (self.freq_stop - self.freq_start) / 4
            painter.drawText(int(x - 25), int(height - 5), f"{freq_val/1e6:.1f}")
        
        # Подпись времени
        painter.drawText(5, int(plot_y + 10), "Время")


class SpectrumPanel(QFrame):
    """Панель со спектром и водопадом"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border: 1px solid #3d3d4f;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Заголовок
        header = QLabel("📊 Спектр в реальном времени")
        header.setStyleSheet("font-size: 14px; font-weight: 600; color: #60a5fa; border: none;")
        layout.addWidget(header)
        
        # Спектр
        self.spectrum = SpectrumWidget()
        layout.addWidget(self.spectrum, 2)
        
        # Водопад
        self.waterfall = WaterfallWidget()
        layout.addWidget(self.waterfall, 1)
        
        # Информация
        info_layout = QHBoxLayout()
        info_layout.setSpacing(20)
        
        self.freq_label = QLabel("Частота: — МГц")
        self.freq_label.setStyleSheet("color: #a1a1aa; font-size: 12px; border: none;")
        info_layout.addWidget(self.freq_label)
        
        self.peak_label = QLabel("Пик: — дБ")
        self.peak_label.setStyleSheet("color: #a1a1aa; font-size: 12px; border: none;")
        info_layout.addWidget(self.peak_label)
        
        self.noise_label = QLabel("Шум: — дБ")
        self.noise_label.setStyleSheet("color: #a1a1aa; font-size: 12px; border: none;")
        info_layout.addWidget(self.noise_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)
    
    def update_spectrum(self, spectrum: np.ndarray, freq_start: float, freq_stop: float):
        """Обновить спектр"""
        self.spectrum.set_spectrum(spectrum, freq_start, freq_stop)
        self.waterfall.set_freq_range(freq_start, freq_stop)
        self.waterfall.add_spectrum(spectrum)
        
        # Обновляем информацию
        self.freq_label.setText(f"Частота: {freq_start/1e6:.1f} - {freq_stop/1e6:.1f} МГц")
        
        if len(spectrum) > 0:
            peak = np.max(spectrum)
            self.peak_label.setText(f"Пик: {peak:.1f} дБ")
    
    def set_threshold(self, threshold_db: float):
        """Установить порог"""
        self.spectrum.set_threshold(threshold_db)
    
    def set_noise_floor(self, noise_floor_db: float):
        """Установить уровень шума"""
        self.spectrum.set_noise_floor(noise_floor_db)
        self.noise_label.setText(f"Шум: {noise_floor_db:.1f} дБ")
