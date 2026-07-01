@echo off
setlocal

set "TARGET_HOST=%~1"
if "%TARGET_HOST%"=="" set "TARGET_HOST=100.70.123.76"

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\remote_logs.ps1" -TargetHost "%TARGET_HOST%" -Project acoustic

exit /b %errorlevel%
