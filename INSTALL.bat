@echo off
chcp 65001 >nul
cd /d "%~dp0"
cls

echo.
echo ========================================
echo      USTANOVKA BIBLIOTEK
echo ========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python ne ustanovlen!
    echo.
    echo Zapustite v PowerShell:
    echo   winget install Python.Python.3.11
    echo.
    echo Potom zakroyte i otkroyte terminal zanovo.
    echo.
    pause
    exit /b 1
)

echo Ustanovka bibliotek...
echo.

python -m pip install pandas openpyxl flask Pillow watchdog python-dotenv

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Oshibka ustanovki!
    pause
    exit /b 1
)

echo.
echo ========================================
echo      USTANOVKA ZAVERSHENA!
echo ========================================
echo.
echo Teper zapuskay: START.bat
echo.
pause
