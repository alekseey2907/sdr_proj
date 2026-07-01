@echo off
REM RF Event Analyzer - Launcher
REM Устанавливает PYTHONPATH и запускает GUI приложение

cd /d "%~dp0"

REM Устанавливаем PYTHONPATH для правильного импорта модулей
set PYTHONPATH=%~dp0src

REM Запускаем приложение
python -c "from rf_analyzer.gui.main_window import run_gui; run_gui()"

REM Если приложение завершилось с ошибкой, показываем сообщение
if errorlevel 1 (
    echo.
    echo Приложение завершилось с ошибкой!
    echo Проверьте logs\rf_analyzer.log для деталей
    pause
)
