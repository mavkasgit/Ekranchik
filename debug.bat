@echo off
cls
title Ekranchik Debug
cd /d "%~dp0"

echo ======================================================
echo       EKRANCHIK DEBUG
echo ======================================================
echo.

echo [1] Python version:
python --version
echo.

echo [2] Python location:
where python
echo.

echo [3] Current directory:
cd
echo.

echo [4] Files exist:
if exist ".env" (echo OK: .env) else (echo ERROR: .env missing!)
if exist "bot.py" (echo OK: bot.py) else (echo ERROR: bot.py missing!)
if exist "app.py" (echo OK: app.py) else (echo ERROR: app.py missing!)
if exist "requirements.txt" (echo OK: requirements.txt) else (echo ERROR: requirements.txt missing!)
echo.

echo [5] Virtual environment:
if exist "venv\Scripts\python.exe" (echo OK: venv exists) else (echo CREATING venv...)
if not exist "venv\Scripts\python.exe" python -m venv venv
echo.

echo [6] Installing dependencies:
"%cd%\venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.

echo [7] Testing bot import:
"%cd%\venv\Scripts\python.exe" -c "import bot; print('[OK] Bot imports successfully')" 2>&1
echo.

echo [8] Testing app import:
"%cd%\venv\Scripts\python.exe" -c "import app; print('[OK] App imports successfully')" 2>&1
echo.

echo ======================================================
echo Debug complete
echo.
pause
