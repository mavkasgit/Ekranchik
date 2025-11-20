@echo off
chcp 65001 >nul
cd /d "%~dp0"
cls
echo.
echo ========================================
echo      INSTALL (first time only)
echo ========================================
echo.

python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python found
    set PY=python
    goto libs
)

echo [!] Python not found
echo.
echo ========================================
echo   INSTALL PYTHON FIRST
echo ========================================
echo.
echo 1. Download: python.org
echo 2. Check "Add Python to PATH"  
echo 3. Run this again
echo.
pause
exit /b 1

:libs
echo [~] Installing libraries (1-2 min)...
%PY% -m pip install --quiet --upgrade pip
%PY% -m pip install --quiet pandas openpyxl flask Pillow watchdog python-dotenv

if %errorlevel% neq 0 (
    echo [ERROR] Installation failed
    pause
    exit /b 1
)
echo [OK] Libraries installed
echo.

if not exist static\images mkdir static\images

if not exist .env (
    echo [~] Creating config...
    echo EXCEL_FILE_PATH=%CD%\data.xlsm> .env
    echo PROFILES_DIR=static/images>> .env
    echo PORT=5000>> .env
    echo DEBUG=True>> .env
    
    echo.
    echo ========================================
    echo   SET EXCEL FILE PATH IN .env
    echo ========================================
    echo.
    echo Opening .env in 2 seconds...
    timeout /t 2 >nul
    notepad .env
) else (
    echo [OK] Config exists
)

echo.
echo ========================================
echo      INSTALLATION COMPLETE!
echo ========================================
echo.
echo Now run: ZAPUSK.bat
echo.
pause
