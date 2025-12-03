@echo off
setlocal enabledelayedexpansion

title Ekranchik Stopper

echo ======================================================
echo       EKRANCHIK BOT STOPPER
echo ======================================================
echo.

echo Killing waitress server...
taskkill /F /IM waitress-serve.exe >nul 2>&1

echo Killing bot process...
taskkill /F /IM python.exe /FI "COMMANDLINE eq *bot.py*" >nul 2>&1

echo.
echo ======================================================
echo Services stopped
echo.
pause
