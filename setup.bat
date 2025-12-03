@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

cls
echo ======================================================
echo       EKRANCHIK - SETUP
echo ======================================================
echo.

REM Find Python
for /f "delims=" %%i in ('where python') do set PYTHON=%%i
if "!PYTHON!"=="" (
    echo [ERROR] Python not found in PATH!
    pause
    exit /b 1
)
echo [OK] Python: !PYTHON!
echo.

REM Create venv
echo [INFO] Creating virtual environment...
"!PYTHON!" -m venv venv
echo [OK] venv created
echo.

REM Install requirements
echo [INFO] Installing dependencies...
"venv\Scripts\python.exe" -m pip install -U pip setuptools wheel
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
echo.

REM Create directories
if not exist "logs" mkdir logs
if not exist "pids" mkdir pids
echo [OK] Directories created
echo.

echo ======================================================
echo [SUCCESS] Setup complete!
echo ======================================================
echo.
echo Now run: start.bat
echo.
pause
