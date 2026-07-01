"""
RF Event Analyzer - Logging Configuration
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(log_file: str = "rf_analyzer.log", log_level: str = "INFO", max_bytes: int = 10485760, backup_count: int = 5):
    """
    Настройка логирования с ротацией файлов
    
    Args:
        log_file: Путь к файлу логов
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        max_bytes: Максимальный размер файла лога (по умолчанию 10MB)
        backup_count: Количество backup файлов
    """
    # Создаём директорию для логов если не существует
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Настройка форматирования
    log_format = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Корневой logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Очищаем существующие handlers
    root_logger.handlers.clear()
    
    # Handler для файла с ротацией
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # В файл пишем всё
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    # Handler для консоли (только WARNING и выше)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # Подавляем предупреждения от сторонних библиотек
    logging.getLogger('rtlsdr').setLevel(logging.ERROR)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    
    logging.info(f"Logging initialized: {log_file} (level={log_level}, max_size={max_bytes/1024/1024:.1f}MB, backups={backup_count})")
    
    return root_logger
