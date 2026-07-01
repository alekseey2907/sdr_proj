@echo off
setlocal

set "TARGET_HOST=%~1"
if "%TARGET_HOST%"=="" set "TARGET_HOST=100.70.123.76"

set "RF_ROOT=/opt/skyshield/sdr_proj"
set "ACOUSTIC_ROOT=/opt/skyshield-acoustic"
set "BRANCH=master"

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\remote_update.ps1" -TargetHost "%TARGET_HOST%" -Project all -Branch "%BRANCH%" -RfRoot "%RF_ROOT%" -AcousticRoot "%ACOUSTIC_ROOT%"

if errorlevel 1 (
  echo.
  echo Combined update failed.
  pause
  exit /b 1
)

echo.
echo RF + Acoustic update finished successfully.
pause
exit /b 0
