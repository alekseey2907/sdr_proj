#!/bin/bash
# Скрипт сборки для Linux
# Запуск: chmod +x build.sh && ./build.sh

set -e

echo "=== RF Event Analyzer Pro - Build Script ==="

# Проверка Python
echo -e "\nChecking Python..."
python3 --version

# Создание venv если не существует
if [ ! -d ".venv" ]; then
    echo -e "\nCreating virtual environment..."
    python3 -m venv .venv
fi

# Активация venv
echo -e "\nActivating virtual environment..."
source .venv/bin/activate

# Установка зависимостей
echo -e "\nInstalling dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# Запуск тестов
echo -e "\nRunning tests..."
pytest tests/ -v

# Сборка
echo -e "\nBuilding executable..."
pip install pyinstaller

# GUI версия
pyinstaller --onefile --windowed \
    --name "rf-analyzer-pro" \
    --add-data "config.yaml:." \
    src/rf_analyzer/gui/main_window.py

# CLI версия
pyinstaller --onefile \
    --name "rf-analyzer" \
    src/rf_analyzer/cli.py

echo -e "\n=== Build completed! ==="
echo "Executables in: dist/"
