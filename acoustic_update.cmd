@echo off
setlocal

set "TARGET_HOST=%~1"
if "%TARGET_HOST%"=="" set "TARGET_HOST=100.70.123.76"
set "ACOUSTIC_ROOT=/opt/skyshield-acoustic"

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\remote_update.ps1" -TargetHost "%TARGET_HOST%" -Project acoustic -Branch master -AcousticRoot "%ACOUSTIC_ROOT%"

if errorlevel 1 (
  echo.
  echo Acoustic update failed.
  pause
  exit /b 1
)

echo.
echo Acoustic update finished successfully.
pause
exit /b 0
