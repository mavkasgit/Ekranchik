@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

title Ekranchik Starter

echo ======================================================
echo       EKRANCHIK BOT STARTER
echo ======================================================
echo.

REM Kill any existing processes
echo [1/5] Killing existing processes...
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM waitress-serve.exe >nul 2>&1
timeout /t 2 >nul

REM Create directories
echo [2/5] Creating directories...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
if not exist "logs" mkdir logs
if not exist "pids" mkdir pids

REM Install dependencies
echo [3/5] Installing dependencies...
"%CD%\venv\Scripts\python.exe" -m pip install -q -r requirements.txt >nul 2>&1

REM Start server (with WebSocket support)
echo [4/5] Starting Flask server...
start "" "%CD%\venv\Scripts\python.exe" app.py
timeout /t 3 >nul

REM Start bot
echo [5/5] Starting Telegram bot...
start "" "%CD%\venv\Scripts\python.exe" bot.py

echo.
echo ======================================================
echo OK - Services restarted!
echo.
pause
