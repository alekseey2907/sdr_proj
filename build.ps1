# Скрипт сборки для Windows
# Запуск: .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== RF Event Analyzer Pro - Build Script ===" -ForegroundColor Cyan

# Проверка Python
Write-Host "`nChecking Python..." -ForegroundColor Yellow
python --version
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python not found!" -ForegroundColor Red
    exit 1
}

# Создание venv если не существует
if (-not (Test-Path ".venv")) {
    Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
}

# Активация venv
Write-Host "`nActivating virtual environment..." -ForegroundColor Yellow
.\.venv\Scripts\Activate.ps1

# Установка зависимостей
Write-Host "`nInstalling dependencies..." -ForegroundColor Yellow
pip install --upgrade pip
pip install -e ".[dev]"

# Запуск тестов
Write-Host "`nRunning tests..." -ForegroundColor Yellow
pytest tests/ -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed!" -ForegroundColor Red
    exit 1
}

# Сборка
Write-Host "`nBuilding executable..." -ForegroundColor Yellow
pip install pyinstaller

# GUI версия
pyinstaller --onefile --windowed `
    --name "RF-Analyzer-Pro" `
    --add-data "config.yaml;." `
    --icon "icon.ico" `
    src/rf_analyzer/gui/main_window.py

# CLI версия  
pyinstaller --onefile `
    --name "rf-analyzer" `
    src/rf_analyzer/cli.py

Write-Host "`n=== Build completed! ===" -ForegroundColor Green
Write-Host "Executables in: dist\" -ForegroundColor Cyan
