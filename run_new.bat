@echo off
chcp 65001 >nul
TITLE SkyShield Launcher
echo ==========================================
echo   🚀 ЗАПУСК СИСТЕМЫ SKYSHIELD
echo ==========================================

:: 1. Запуск Базы Данных (Docker)
echo.
echo [1/3] Запускаем Database (Docker)...
cd backend
docker-compose up -d db
if %errorlevel% neq 0 (
    echo ⚠️  Docker не найден или вернул ошибку. Пропускаем шаг...
) else (
    echo ✅ БД запущена успешно.
)
cd ..

:: Ждем поднятия базы
echo ⏳ Ждем 5 секунд инициализацию БД...
timeout /t 5 /nobreak >nul

:: 2. Запуск Backend API
echo.
echo [2/3] Запускаем Backend API...
:: Важно: подключаемся к localhost:5433 (так как проброшено из Docker)
start "SkyShield Backend" cmd /k "set DATABASE_URL=postgresql+asyncpg://postgres:postgres_password@localhost:5433/iot_db&& cd backend && ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

:: 3. Запуск SDR Worker
echo.
echo [3/3] Запускаем SDR Worker (Детектор)...
start "SkyShield Worker" cmd /k ".venv\Scripts\python.exe src\sdr_worker.py"

echo.
echo ==========================================
echo   ✅ СИСТЕМА ЗАПУЩЕНА
echo.
echo   📊 Дашборд: http://localhost:8000/dashboard
echo   📄 API Docs: http://localhost:8000/docs
echo ==========================================
pause
