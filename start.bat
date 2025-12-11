@echo off
chcp 65001 >nul
echo.
echo ========================================
echo SYSTEM CONTROLLER
echo ========================================
echo.
echo Starting all services...
echo.
python start.py
echo.
pause
