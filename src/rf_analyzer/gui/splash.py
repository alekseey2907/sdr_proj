"""
RF Event Analyzer - Splash Screen
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QBrush, QPen


class ModernSplashScreen(QSplashScreen):
    """Современный сплэш-экран с прогресс-баром"""
    
    def __init__(self):
        # Создаём pixmap с градиентным фоном
        pixmap = QPixmap(500, 350)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Градиентный фон
        gradient = QLinearGradient(0, 0, 0, 350)
        gradient.setColorAt(0, QColor(30, 30, 46))
        gradient.setColorAt(1, QColor(20, 20, 35))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 500, 350, 20, 20)
        
        # Рамка
        painter.setPen(QPen(QColor(61, 61, 79), 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(1, 1, 498, 348, 20, 20)
        
        # Иконка (эмодзи)
        painter.setFont(QFont("Segoe UI Emoji", 48))
        painter.setPen(QColor(96, 165, 250))
        painter.drawText(pixmap.rect().adjusted(0, 40, 0, -150), Qt.AlignCenter, "📡")
        
        # Название
        painter.setFont(QFont("Segoe UI", 28, QFont.Bold))
        painter.setPen(QColor(228, 228, 231))
        painter.drawText(pixmap.rect().adjusted(0, 110, 0, -100), Qt.AlignCenter, "RF Event Analyzer")
        
        # Подзаголовок
        painter.setFont(QFont("Segoe UI", 14))
        painter.setPen(QColor(96, 165, 250))
        painter.drawText(pixmap.rect().adjusted(0, 160, 0, -80), Qt.AlignCenter, "Professional Edition")
        
        # Версия
        painter.setFont(QFont("Segoe UI", 11))
        painter.setPen(QColor(113, 113, 122))
        painter.drawText(pixmap.rect().adjusted(0, 190, 0, -60), Qt.AlignCenter, "Версия 1.0.0")
        
        # Прогресс-бар фон
        painter.setBrush(QColor(45, 45, 61))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(50, 270, 400, 8, 4, 4)
        
        # Copyright
        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor(113, 113, 122))
        painter.drawText(pixmap.rect().adjusted(0, 0, 0, -15), Qt.AlignBottom | Qt.AlignHCenter, "© 2024 RF Solutions")
        
        painter.end()
        
        super().__init__(pixmap)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        self.progress = 0
        self.message = "Инициализация..."
    
    def set_progress(self, value: int, message: str = ""):
        """Установить прогресс загрузки"""
        self.progress = min(100, max(0, value))
        if message:
            self.message = message
        self.repaint()
    
    def drawContents(self, painter: QPainter):
        """Отрисовка прогресс-бара и сообщения"""
        # Прогресс-бар
        bar_width = int(400 * self.progress / 100)
        if bar_width > 0:
            gradient = QLinearGradient(50, 0, 450, 0)
            gradient.setColorAt(0, QColor(26, 115, 232))
            gradient.setColorAt(1, QColor(96, 165, 250))
            painter.setBrush(QBrush(gradient))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(50, 270, bar_width, 8, 4, 4)
        
        # Сообщение
        painter.setFont(QFont("Segoe UI", 11))
        painter.setPen(QColor(161, 161, 170))
        painter.drawText(50, 300, 400, 30, Qt.AlignCenter, self.message)


def show_splash(app, duration_ms: int = 2000):
    """Показать сплэш-экран"""
    splash = ModernSplashScreen()
    splash.show()
    app.processEvents()
    
    # Симуляция загрузки
    steps = [
        (10, "Загрузка конфигурации..."),
        (30, "Инициализация хранилища..."),
        (50, "Проверка лицензии..."),
        (70, "Загрузка интерфейса..."),
        (90, "Подготовка к работе..."),
        (100, "Готово!"),
    ]
    
    step_duration = duration_ms // len(steps)
    
    for progress, message in steps:
        splash.set_progress(progress, message)
        app.processEvents()
        QTimer.singleShot(step_duration, lambda: None)
        # Небольшая задержка
        import time
        time.sleep(step_duration / 1000)
    
    return splash
