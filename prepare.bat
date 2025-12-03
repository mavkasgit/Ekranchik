@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

cls
echo ======================================================
echo       EKRANCHIK - FINAL PREPARATION
echo ======================================================
echo.

REM Check Python
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Python not found in PATH!
    echo Install Python 3.11+ and add to PATH
    pause
    exit /b 1
)
echo [OK] Python found

REM Check .env
if not exist ".env" (
    echo [ERROR] .env file missing!
    echo Create .env with TELEGRAM_TOKEN and BOT_PASSWORD
    pause
    exit /b 1
)
echo [OK] .env exists

REM Create venv if needed
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)
echo [OK] venv ready

REM Create directories
if not exist "logs" mkdir logs
if not exist "pids" mkdir pids
echo [OK] Directories ready

REM Install dependencies
echo [INFO] Installing dependencies...
"%cd%\venv\Scripts\python.exe" -m pip install -q -r requirements.txt 2>nul
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

REM Test imports
echo [INFO] Testing imports...
"%cd%\venv\Scripts\python.exe" -c "import bot" >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] bot.py has errors
    pause
    exit /b 1
)
echo [OK] bot.py OK

"%cd%\venv\Scripts\python.exe" -c "import app" >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] app.py has errors
    pause
    exit /b 1
)
echo [OK] app.py OK

REM Kill old processes
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM waitress-serve.exe >nul 2>&1
timeout /t 1 >nul

echo.
echo ======================================================
echo [SUCCESS] All ready! Starting services...
echo ======================================================
echo.

REM Start services
start "" "%cd%\venv\Scripts\waitress-serve.exe" --host=0.0.0.0 --port=5000 app:app
timeout /t 2 >nul

start "" "%cd%\venv\Scripts\python.exe" bot.py

echo.
echo [OK] Services started!
echo Bot running on Telegram
echo Web interface: http://localhost:5000
echo.
pause
