@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

cls
echo ======================================================
echo       FINAL INSTALLATION
echo ======================================================
echo.

REM Kill all Python
taskkill /F /IM python.exe >nul 2>&1
taskkill /F /IM waitress-serve.exe >nul 2>&1
timeout /t 1 >nul

REM Remove old venv
echo [1] Removing old venv...
if exist "venv" (
    rmdir /s /q venv
)
echo [OK]
echo.

REM Create fresh venv
echo [2] Creating fresh virtual environment...
python -m venv venv
if !errorlevel! neq 0 (
    echo [ERROR] Failed to create venv
    pause
    exit /b 1
)
echo [OK]
echo.

REM Install packages with exact versions
echo [3] Installing packages (THIS WILL TAKE TIME)...
venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
venv\Scripts\python.exe -m pip install -r requirements.txt

if !errorlevel! neq 0 (
    echo [ERROR] Failed to install packages
    pause
    exit /b 1
)
echo [OK]
echo.

REM Test import
echo [4] Testing bot import...
venv\Scripts\python.exe -c "import bot; print('[OK] Bot imports successfully')" 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Bot import failed
    pause
    exit /b 1
)
echo [OK]
echo.

REM Create directories
if not exist "logs" mkdir logs
if not exist "pids" mkdir pids
echo [OK] Directories created
echo.

echo ======================================================
echo [SUCCESS] Installation complete!
echo ======================================================
echo.
echo Now run: start.bat
echo.
pause
