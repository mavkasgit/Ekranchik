@echo off
chcp 65001 >nul
cd /d "%~dp0"
cls
echo.
echo ========================================
echo           START SERVER
echo ========================================
echo.

if exist python.exe (
    set PY=python.exe
) else (
    set PY=python
)

%PY% -c "import flask" 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Libraries not installed!
    echo.
    echo Run first: USTANOVKA.bat
    echo.
    pause
    exit /b 1
)

if not exist .env (
    echo [ERROR] File .env not found!
    echo.
    echo Run first: USTANOVKA.bat
    echo.
    pause
    exit /b 1
)

echo [OK] Starting server...
echo.
echo ========================================
echo   Open: http://localhost:5000
echo   Stop: Ctrl+C
echo ========================================
echo.

timeout /t 1 >nul
start http://localhost:5000
%PY% app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to start!
    echo Check Excel path in .env
    echo.
    pause
)
