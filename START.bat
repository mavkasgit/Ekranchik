@echo off
chcp 65001 >nul
cd /d "%~dp0"
cls

echo.
echo ========================================
echo           ZAPUSK SERVERA
echo ========================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python ne nayden!
    echo.
    echo Ustanovite: winget install Python.Python.3.11
    echo.
    pause
    exit /b 1
)

if not exist .env (
    echo [!] Fayl .env ne nayden!
    echo Sozdayu shablon...
    (
        echo EXCEL_FILE_PATH=%CD%\data.xlsm
        echo PROFILES_DIR=static/images
        echo PORT=5000
        echo DEBUG=True
    ) > .env
    echo.
    echo Otkroetsya .env - ukazhite put k Excel
    timeout /t 2 >nul
    notepad .env
    echo.
)

echo Vybor rezhima zapuska:
echo.
echo 1. S oknom CMD (mozhno videt logi)
echo 2. Skryt v fone (bez okna CMD)
echo.
set /p choice="Vvedite 1 ili 2: "

if "%choice%"=="2" (
    echo.
    echo Zapusk v fonovom rezhime...
    echo Server budet rabotat bez okna CMD
    echo Chtoby ostanovit - zakriy cherez Task Manager
    echo.
    timeout /t 2 >nul
    start http://localhost:5000
    start /min pythonw app.py
    exit
) else (
    echo.
    echo Zapusk s oknom CMD...
    echo.
    timeout /t 1 >nul
    start http://localhost:5000
    python app.py
    
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Oshibka zapuska!
        echo.
        pause
    )
)
