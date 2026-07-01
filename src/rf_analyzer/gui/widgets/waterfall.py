"""
RF Event Analyzer - Waterfall Display Widget
"""
from __future__ import annotations

import numpy as np
from collections import deque
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QLinearGradient, QPen

if TYPE_CHECKING:
    from numpy.typing import NDArray


class WaterfallWidget(QWidget):
    """Виджет отображения водопада (waterfall) спектра"""
    
    # Сигнал обновления
    updated = Signal()
    
    def __init__(self, parent=None, history_size: int = 200):
        super().__init__(parent)
        
        # Ограничиваем историю для предотвращения утечек памяти
        self.history_size = min(history_size, 500)  # макс 500 строк
        self._history: deque = deque(maxlen=self.history_size)
        self._fft_size = 1024
        self._min_db = -100.0
        self._max_db = 60.0
        self._center_freq = 100e6
        self._sample_rate = 2.0e6
        
        # Цветовая карта (от синего через зелёный к красному)
        self._colormap = self._create_colormap()
        
        self._setup_ui()
        
        # Таймер обновления
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_display)
        self._update_timer.start(20)  # 100 FPS
    
    def _setup_ui(self):
        """Настройка интерфейса"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        
        # Заголовок с частотой
        self.freq_label = QLabel("Waterfall")
        self.freq_label.setAlignment(Qt.AlignCenter)
        self.freq_label.setStyleSheet("""
            QLabel {
                color: #a1a1aa;
                font-size: 11px;
                padding: 2px;
            }
        """)
        layout.addWidget(self.freq_label)
        
        # Виджет для отображения изображения
        self.image_label = QLabel()
        self.image_label.setMinimumSize(200, 150)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1e1e2e; border-radius: 4px;")
        layout.addWidget(self.image_label)
        
        # Шкала уровня
        self.level_label = QLabel(f"{self._min_db:.0f} dB — {self._max_db:.0f} dB")
        self.level_label.setAlignment(Qt.AlignCenter)
        self.level_label.setStyleSheet("""
            QLabel {
                color: #71717a;
                font-size: 10px;
            }
        """)
        layout.addWidget(self.level_label)
    
    def _create_colormap(self, size: int = 256) -> list[QColor]:
        """Создать цветовую карту"""
        colors = []
        for i in range(size):
            ratio = i / (size - 1)
            
            if ratio < 0.25:
                # Чёрный -> Синий
                r, g, b = 0, 0, int(ratio * 4 * 255)
            elif ratio < 0.5:
                # Синий -> Голубой
                r = 0
                g = int((ratio - 0.25) * 4 * 255)
                b = 255
            elif ratio < 0.75:
                # Голубой -> Жёлтый
                r = int((ratio - 0.5) * 4 * 255)
                g = 255
                b = int((1 - (ratio - 0.5) * 4) * 255)
            else:
                # Жёлтый -> Красный
                r = 255
                g = int((1 - (ratio - 0.75) * 4) * 255)
                b = 0
            
            colors.append(QColor(r, g, b))
        
        return colors
    
    def add_spectrum(self, power_db: NDArray[np.float64], 
                     center_freq: float = None,
                     sample_rate: float = None) -> None:
        """Добавить строку спектра"""
        if power_db is None or len(power_db) == 0:
            return
            
        if center_freq:
            self._center_freq = center_freq
        if sample_rate:
            self._sample_rate = sample_rate
        
        # Ресемплируем до нужного размера если нужно
        if len(power_db) != self._fft_size:
            indices = np.linspace(0, len(power_db) - 1, self._fft_size).astype(int)
            power_db = power_db[indices]
        
        # Нормализуем
        normalized = np.clip(
            (power_db - self._min_db) / (self._max_db - self._min_db),
            0, 1
        )
        
        self._history.append(normalized)
        
        # Немедленно обновляем отображение
        self._update_display()
    
    def set_range(self, min_db: float, max_db: float) -> None:
        """Установить диапазон отображения"""
        self._min_db = min_db
        self._max_db = max_db
        self.level_label.setText(f"{min_db:.0f} dB — {max_db:.0f} dB")
    
    def clear(self) -> None:
        """Очистить историю"""
        self._history.clear()
    
    def _update_display(self) -> None:
        """Обновить отображение"""
        if not self._history:
            return
        
        width = self.image_label.width()
        height = self.image_label.height()
        
        if width < 10 or height < 10:
            return
        
        # Совпадение с margin'ами из SpectrumWidget
        margin_left = 50
        margin_right = 10
        plot_width = width - margin_left - margin_right
        
        try:
            # Создаём изображение
            history_len = len(self._history)
            img_height = min(history_len, height)
            img_width = self._fft_size
            
            # Создаём массив пикселей с учётом margin'ов
            image = QImage(width, img_height, QImage.Format_RGB32)
            image.fill(QColor(30, 30, 46))  # Фон как у спектра
            
            # Заполняем изображение (сверху вниз: новые строки вверху)
            for y in range(img_height):
                row_idx = history_len - 1 - y  # Инвертируем: последняя строка -> y=0
                if row_idx < 0 or row_idx >= history_len:
                    continue
                
                row = self._history[row_idx]
                # Заполняем все пиксели plot_width, растягивая bins
                for x_offset in range(0, plot_width, 2):  # Шаг 2 для ускорения
                    try:
                        # Находим соответствующий bin для этого пикселя
                        bin_idx = int(x_offset * img_width / plot_width)
                        bin_idx = min(bin_idx, len(row) - 1)
                        
                        x = margin_left + x_offset
                        color_idx = min(255, max(0, int(row[bin_idx] * 255)))
                        color = self._colormap[color_idx]
                        image.setPixelColor(x, y, color)
                        # Заполняем следующий пиксель тем же цветом
                        if x_offset + 1 < plot_width:
                            image.setPixelColor(x + 1, y, color)
                    except (IndexError, ValueError):
                        pass
            
            # Масштабируем только по высоте (ширина уже правильная)
            scaled = image.scaled(width, height, Qt.IgnoreAspectRatio, Qt.FastTransformation)
            self.image_label.setPixmap(QPixmap.fromImage(scaled))
            
            # Обновляем заголовок
            freq_mhz = self._center_freq / 1e6
            bw_mhz = self._sample_rate / 1e6
            self.freq_label.setText(f"{freq_mhz:.3f} MHz ± {bw_mhz/2:.1f} MHz")
        except Exception as e:
            # Логируем ошибки но не прерываем работу
            import logging
            logging.getLogger(__name__).debug(f"Waterfall update error: {e}")


class SpectrumWidget(QWidget):
    """Виджет отображения спектра в реальном времени"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._power_db: NDArray[np.float64] | None = None
        self._min_db = -100.0
        self._max_db = 60.0
        self._center_freq = 100e6
        self._sample_rate = 2.0e6
        self._threshold_db = -60.0
        
        # Trace Hold данные
        self._trace_hold_enabled = True
        self._trace_hold_data: NDArray[np.float64] | None = None
        
        # Маркеры: {id: {'freq_mhz': float, 'power_main_db': float, 'power_trace_db': float}}
        self._markers = {}
        self._selected_marker_id = None
        self._max_markers = 10
        self._last_click_time = 0
        self._double_click_threshold = 0.3  # секунды
        self._dragging_marker = None  # ID перемещаемого маркера
        
        self.setMinimumSize(200, 100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        
        # Таймер перерисовки
        self._timer = QTimer()
        self._timer.timeout.connect(self.update)
        self._timer.start(10)  # 200 FPS
    
    def set_spectrum(self, power_db: NDArray[np.float64],
                     center_freq: float = None,
                     sample_rate: float = None) -> None:
        """Установить данные спектра"""
        self._power_db = power_db.copy()
        if center_freq:
            self._center_freq = center_freq
        if sample_rate:
            self._sample_rate = sample_rate
        
        # Обновляем Trace Hold если включен
        if self._trace_hold_enabled:
            if self._trace_hold_data is None or len(self._trace_hold_data) != len(power_db):
                # Инициализируем или переинициализируем при изменении размера
                self._trace_hold_data = power_db.copy()
            else:
                # Сохраняем максимумы
                self._trace_hold_data = np.maximum(self._trace_hold_data, power_db)
    
    def set_range(self, min_db: float, max_db: float) -> None:
        """Установить диапазон"""
        self._min_db = min_db
        self._max_db = max_db
    
    def set_threshold(self, threshold_db: float) -> None:
        """Установить порог детекции"""
        self._threshold_db = threshold_db
    
    def set_trace_hold_enabled(self, enabled: bool) -> None:
        """Включить/выключить Trace Hold"""
        self._trace_hold_enabled = enabled
        if not enabled:
            self._trace_hold_data = None
    
    def reset_trace_hold(self) -> None:
        """Сбросить накопленные максимумы Trace Hold"""
        self._trace_hold_data = None
    
    def _get_power_at_frequency(self, freq_mhz: float) -> tuple[float | None, float | None]:
        """Получить мощность на заданной частоте из текущих данных спектра и Trace Hold"""
        if self._power_db is None or len(self._power_db) == 0:
            return None, None
        
        # Вычисляем частотный диапазон
        bw = self._sample_rate
        start_freq = (self._center_freq - bw / 2) / 1e6
        stop_freq = (self._center_freq + bw / 2) / 1e6
        bw_mhz = stop_freq - start_freq
        
        # Проверяем что частота в диапазоне
        if freq_mhz < start_freq or freq_mhz > stop_freq:
            return None, None
        
        # Находим индекс в массиве спектра
        freq_ratio = (freq_mhz - start_freq) / bw_mhz
        idx = int(freq_ratio * len(self._power_db))
        idx = max(0, min(idx, len(self._power_db) - 1))
        
        # Получаем мощность из основного спектра
        power_main = float(self._power_db[idx])
        
        # Получаем мощность из Trace Hold если доступно
        power_trace = None
        if self._trace_hold_enabled and self._trace_hold_data is not None and idx < len(self._trace_hold_data):
            power_trace = float(self._trace_hold_data[idx])
        
        return power_main, power_trace
    
    def add_marker(self, freq_mhz: float, power_main_db: float, power_trace_db: float | None = None) -> int | None:
        """Добавить маркер. Возвращает ID маркера или None если лимит"""
        if len(self._markers) >= self._max_markers:
            return None
        
        # Находим первый свободный ID (M1-M10)
        for i in range(1, self._max_markers + 1):
            if i not in self._markers:
                self._markers[i] = {
                    'freq_mhz': freq_mhz,
                    'power_main_db': power_main_db,
                    'power_trace_db': power_trace_db
                }
                return i
        return None
    
    def remove_marker(self, marker_id: int) -> None:
        """Удалить маркер по ID"""
        if marker_id in self._markers:
            del self._markers[marker_id]
            if self._selected_marker_id == marker_id:
                self._selected_marker_id = None
    
    def clear_all_markers(self) -> None:
        """Удалить все маркеры"""
        self._markers.clear()
        self._selected_marker_id = None
    
    def get_selected_marker_id(self) -> int | None:
        """Получить ID выбранного маркера"""
        return self._selected_marker_id
    
    def get_markers(self) -> dict:
        """Получить все маркеры"""
        return self._markers.copy()
    
    def update_marker(self, marker_id: int, freq_mhz: float) -> None:
        """Обновить позицию маркера и пересчитать мощности"""
        if marker_id not in self._markers or self._power_db is None:
            return
        
        # Вычисляем bin для новой частоты
        bw_mhz = self._sample_rate / 1e6
        start_freq = self._center_freq / 1e6 - bw_mhz / 2
        freq_ratio = (freq_mhz - start_freq) / bw_mhz
        freq_ratio = max(0, min(1, freq_ratio))
        
        bin_idx = int(freq_ratio * len(self._power_db))
        bin_idx = max(0, min(len(self._power_db) - 1, bin_idx))
        
        # Обновляем мощность на основной линии
        power_main = self._power_db[bin_idx]
        
        # Обновляем мощность на Trace Hold
        power_trace = None
        if self._trace_hold_enabled and self._trace_hold_data is not None and bin_idx < len(self._trace_hold_data):
            power_trace = self._trace_hold_data[bin_idx]
        
        self._markers[marker_id] = {
            'freq_mhz': freq_mhz,
            'power_main_db': power_main,
            'power_trace_db': power_trace
        }
    
    def set_markers(self, markers: dict) -> None:
        """Установить маркеры (для загрузки из файла)"""
        self._markers = markers.copy()
        self._selected_marker_id = None
    
    def mouseDoubleClickEvent(self, event):
        """Обработка двойного клика - добавление маркера"""
        if event.button() == Qt.LeftButton:
            self._add_marker_at_position(event.pos())
    
    def mousePressEvent(self, event):
        """Обработка одинарного клика - выделение маркера"""
        if event.button() == Qt.LeftButton:
            self._select_marker_at_position(event.pos())
            # Если выбрали маркер, начинаем drag
            if self._selected_marker_id is not None:
                self._dragging_marker = self._selected_marker_id
    
    def mouseMoveEvent(self, event):
        """Обработка перемещения мыши - drag маркера"""
        if self._dragging_marker is not None and self._power_db is not None:
            margin_left = 50
            margin_right = 10
            plot_width = self.width() - margin_left - margin_right
            
            # Проверяем что мышь в пределах графика
            if event.pos().x() >= margin_left and event.pos().x() <= margin_left + plot_width:
                x_rel = event.pos().x() - margin_left
                freq_ratio = x_rel / plot_width
                bw_mhz = self._sample_rate / 1e6
                start_freq = self._center_freq / 1e6 - bw_mhz / 2
                freq_mhz = start_freq + freq_ratio * bw_mhz
                
                # Обновляем позицию маркера
                self.update_marker(self._dragging_marker, freq_mhz)
    
    def mouseReleaseEvent(self, event):
        """Обработка отпускания кнопки мыши - завершение drag"""
        if event.button() == Qt.LeftButton:
            self._dragging_marker = None
    
    def _add_marker_at_position(self, pos):
        """Добавить маркер в позиции клика"""
        if self._power_db is None:
            return
        
        margin_left = 50
        margin_right = 10
        margin_top = 20
        margin_bottom = 30
        
        plot_width = self.width() - margin_left - margin_right
        
        # Проверяем что клик внутри графика
        if pos.x() < margin_left or pos.x() > margin_left + plot_width:
            return
        
        # Вычисляем частоту
        x_rel = pos.x() - margin_left
        freq_ratio = x_rel / plot_width
        bw_mhz = self._sample_rate / 1e6
        start_freq = self._center_freq / 1e6 - bw_mhz / 2
        freq_mhz = start_freq + freq_ratio * bw_mhz
        
        # Находим ближайший bin
        bin_idx = int(freq_ratio * len(self._power_db))
        bin_idx = max(0, min(len(self._power_db) - 1, bin_idx))
        
        # Определяем мощность на основной линии
        power_main = self._power_db[bin_idx]
        
        # Определяем мощность на Trace Hold (если есть)
        power_trace = None
        if self._trace_hold_enabled and self._trace_hold_data is not None and bin_idx < len(self._trace_hold_data):
            power_trace = self._trace_hold_data[bin_idx]
        
        # Добавляем маркер с обеими мощностями
        marker_id = self.add_marker(freq_mhz, power_main, power_trace)
        if marker_id:
            self._selected_marker_id = marker_id
    
    def _select_marker_at_position(self, pos):
        """Выделить маркер в позиции клика"""
        if not self._markers:
            self._selected_marker_id = None
            return
        
        margin_left = 50
        margin_right = 10
        plot_width = self.width() - margin_left - margin_right
        
        bw_mhz = self._sample_rate / 1e6
        start_freq = self._center_freq / 1e6 - bw_mhz / 2
        
        # Ищем ближайший маркер (в пределах 10 пикселей)
        min_dist = 10
        closest_id = None
        
        for marker_id, marker_data in self._markers.items():
            freq_mhz = marker_data['freq_mhz']
            freq_ratio = (freq_mhz - start_freq) / bw_mhz
            x = margin_left + int(freq_ratio * plot_width)
            
            dist = abs(pos.x() - x)
            if dist < min_dist:
                min_dist = dist
                closest_id = marker_id
        
        self._selected_marker_id = closest_id
    
    def paintEvent(self, event):
        """Отрисовка спектра"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height()
        margin_left = 50
        margin_right = 10
        margin_top = 20
        margin_bottom = 30
        
        plot_width = width - margin_left - margin_right
        plot_height = height - margin_top - margin_bottom
        
        # Фон
        painter.fillRect(0, 0, width, height, QColor(30, 30, 46))
        
        if self._power_db is None or len(self._power_db) == 0:
            painter.setPen(QColor(113, 113, 122))
            painter.drawText(self.rect(), Qt.AlignCenter, "No data")
            return
        
        # Сетка мощности (5 линий)
        painter.setPen(QColor(61, 61, 79))
        painter.setFont(self.font())
        for i in range(6):  # 0, 1, 2, 3, 4, 5
            y = margin_top + int(plot_height * i / 5)
            painter.drawLine(margin_left, y, margin_left + plot_width, y)
            
            # Подписи мощности
            db_value = self._max_db - (self._max_db - self._min_db) * i / 5
            painter.setPen(QColor(161, 161, 170))
            painter.drawText(5, y + 5, f"{db_value:.0f}")
            painter.setPen(QColor(61, 61, 79))
        
        # Сетка частоты (10 линий)
        freq_mhz = self._center_freq / 1e6
        bw_mhz = self._sample_rate / 1e6
        start_freq = freq_mhz - bw_mhz / 2
        stop_freq = freq_mhz + bw_mhz / 2
        
        for i in range(11):  # 0 до 10
            x = margin_left + int(plot_width * i / 10)
            painter.drawLine(x, margin_top, x, margin_top + plot_height)
            
            # Подписи частоты
            freq_value = start_freq + (stop_freq - start_freq) * i / 10
            painter.setPen(QColor(161, 161, 170))
            label = f"{freq_value:.2f}" if bw_mhz < 10 else f"{freq_value:.1f}"
            painter.drawText(x - 20, height - 5, label)
            painter.setPen(QColor(61, 61, 79))
        
        # Порог
        threshold_norm = (self._threshold_db - self._min_db) / (self._max_db - self._min_db)
        threshold_y = margin_top + int(plot_height * (1 - threshold_norm))
        painter.setPen(QColor(248, 113, 113, 150))
        painter.drawLine(margin_left, threshold_y, margin_left + plot_width, threshold_y)
        
        # Рамка графика
        painter.setPen(QColor(77, 77, 95))
        painter.drawRect(margin_left, margin_top, plot_width, plot_height)
        
        # Спектр
        painter.setPen(QColor(96, 165, 250, 255))
        
        # Рисуем спектр
        points = []
        n = len(self._power_db)
        
        for i in range(n):
            x = margin_left + int(i * plot_width / n)
            db = self._power_db[i]
            normalized = (db - self._min_db) / (self._max_db - self._min_db)
            normalized = max(0, min(1, normalized))
            y = margin_top + int(plot_height * (1 - normalized))
            points.append((x, y))
        
        # Рисуем линию
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            painter.drawLine(x1, y1, x2, y2)
        
        # Рисуем Trace Hold поверх спектра (если включен)
        if self._trace_hold_enabled and self._trace_hold_data is not None:
            painter.setPen(QColor(248, 113, 113, 200))  # Красная линия
            
            trace_points = []
            n_trace = len(self._trace_hold_data)
            
            for i in range(n_trace):
                x = margin_left + int(i * plot_width / n_trace)
                db = self._trace_hold_data[i]
                normalized = (db - self._min_db) / (self._max_db - self._min_db)
                normalized = max(0, min(1, normalized))
                y = margin_top + int(plot_height * (1 - normalized))
                trace_points.append((x, y))
            
            # Рисуем красную линию Trace Hold
            for i in range(len(trace_points) - 1):
                x1, y1 = trace_points[i]
                x2, y2 = trace_points[i + 1]
                painter.drawLine(x1, y1, x2, y2)
        
        # Заливка под спектром
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(96, 165, 250, 50))
        
        from PySide6.QtGui import QPolygon
        from PySide6.QtCore import QPoint
        
        polygon_points = [QPoint(margin_left, margin_top + plot_height)]
        for x, y in points:
            polygon_points.append(QPoint(x, y))
        polygon_points.append(QPoint(margin_left + plot_width, margin_top + plot_height))
        
        painter.drawPolygon(QPolygon(polygon_points))
        
        # Подписи начала и конца диапазона
        painter.setPen(QColor(161, 161, 170))
        painter.setFont(self.font())
        painter.drawText(margin_left, margin_top - 5, f"▼ {start_freq:.2f} MHz")
        painter.drawText(margin_left + plot_width - 80, margin_top - 5, f"{stop_freq:.2f} MHz ▼")
        
        # Рисуем маркеры
        self._draw_markers(painter, margin_left, margin_top, margin_bottom, plot_width, plot_height, start_freq, bw_mhz)
    
    def _draw_markers(self, painter, margin_left, margin_top, margin_bottom, plot_width, plot_height, start_freq, bw_mhz):
        """Отрисовка маркеров"""
        if not self._markers:
            return
        
        from PySide6.QtGui import QFont
        
        for marker_id, marker_data in self._markers.items():
            freq_mhz = marker_data['freq_mhz']
            
            # Получаем актуальную мощность в реальном времени
            power_main_db, power_trace_db = self._get_power_at_frequency(freq_mhz)
            
            # Если частота вне диапазона, пропускаем
            if power_main_db is None:
                continue
            
            # Вычисляем X-координату
            freq_ratio = (freq_mhz - start_freq) / bw_mhz
            
            # Проверяем что маркер в видимой области
            if freq_ratio < 0 or freq_ratio > 1:
                continue
            
            x = margin_left + int(freq_ratio * plot_width)
            
            # Определяем цвет (зеленый для обычного, ярко-зеленый для выделенного)
            is_selected = (marker_id == self._selected_marker_id)
            if is_selected:
                line_color = QColor(34, 197, 94, 255)  # Ярко-зеленый
                line_width = 2
            else:
                line_color = QColor(34, 197, 94, 180)  # Зеленый полупрозрачный
                line_width = 1
            
            # Рисуем вертикальную линию
            painter.setPen(QPen(line_color, line_width))
            painter.drawLine(x, margin_top, x, margin_top + plot_height)
            
            # Формируем текст с обеими мощностями
            text_lines = [f"M{marker_id}: {freq_mhz:.3f} MHz"]
            text_lines.append(f"SP: {power_main_db:.1f} dB")  # Spectrum
            if power_trace_db is not None:
                text_lines.append(f"TH: {power_trace_db:.1f} dB")  # Trace Hold
            
            # Настройка шрифта
            font = QFont()
            font.setPixelSize(10)
            font.setBold(is_selected)
            painter.setFont(font)
            
            # Вычисляем размер текста
            text_width = max(painter.fontMetrics().boundingRect(line).width() for line in text_lines) + 8
            line_height = painter.fontMetrics().height()
            text_height = len(text_lines) * line_height + 6
            
            # Позиция текста (сначала пробуем сверху маркера)
            text_x = x - text_width // 2
            text_y = margin_top - text_height - 5
            
            # Если текст выходит за верхнюю границу, рисуем внутри графика
            if text_y < 0:
                text_y = margin_top + 10
            
            # Корректируем если выходит за границы по горизонтали
            if text_x < margin_left:
                text_x = margin_left
            if text_x + text_width > margin_left + plot_width:
                text_x = margin_left + plot_width - text_width
            
            # Рисуем фон текста
            painter.setPen(Qt.NoPen)
            bg_color = QColor(30, 30, 46, 220) if not is_selected else QColor(34, 197, 94, 50)
            painter.setBrush(bg_color)
            painter.drawRect(text_x, text_y, text_width, text_height)
            
            # Рисуем текст
            painter.setPen(line_color)
            for i, line in enumerate(text_lines):
                painter.drawText(text_x + 4, text_y + 12 + i * line_height, line)
