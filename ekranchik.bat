@echo off
title Ekranchik Docker Manager

:menu
cls
echo ========================================
echo     EKRANCHIK DOCKER MANAGER
echo ========================================
echo.

REM Check container status
docker ps 2>nul | findstr "ekranchik-app" >nul 2>&1
if %errorlevel% equ 0 (
    echo [STATUS] OK Container is RUNNING
    echo          Web: http://localhost:5000
) else (
    echo [STATUS] X Container is STOPPED
)
echo.
echo ========================================
echo  1. Start
echo  2. Stop
echo  3. Restart
echo  4. Rebuild
echo  5. Logs (real-time)
echo  6. Status
echo  7. Open Web (http://localhost:5000)
echo  0. Exit
echo ========================================
echo.
set /p choice=Choose action (0-7): 

if "%choice%"=="1" goto start
if "%choice%"=="2" goto stop
if "%choice%"=="3" goto restart
if "%choice%"=="4" goto rebuild
if "%choice%"=="5" goto logs
if "%choice%"=="6" goto status
if "%choice%"=="7" goto web
if "%choice%"=="0" goto end
goto menu

:start
cls
echo ========================================
echo   STARTING EKRANCHIK
echo ========================================
echo.
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop is not running!
    echo Start Docker Desktop and try again.
    pause
    goto menu
)
echo [OK] Docker is running
echo.
echo Starting containers...
docker-compose up -d
if %errorlevel% equ 0 (
    echo.
    echo OK Ekranchik started successfully!
    echo.
    echo Web: http://localhost:5000
    echo Telegram bot: active (password: 1122)
    echo.
) else (
    echo [ERROR] Failed to start!
)
pause
goto menu

:stop
cls
echo ========================================
echo   STOPPING EKRANCHIK
echo ========================================
echo.
docker-compose down
if %errorlevel% equ 0 (
    echo OK Containers stopped
) else (
    echo [ERROR] Failed to stop
)
echo.
pause
goto menu

:restart
cls
echo ========================================
echo   RESTARTING EKRANCHIK
echo ========================================
echo.
echo Stopping...
docker-compose down
echo.
echo Starting...
docker-compose up -d
if %errorlevel% equ 0 (
    echo.
    echo OK Restarted successfully!
    echo Web: http://localhost:5000
) else (
    echo [ERROR] Failed to restart
)
echo.
pause
goto menu

:rebuild
cls
echo ========================================
echo   REBUILDING EKRANCHIK
echo ========================================
echo.
echo WARNING: Full rebuild!
echo This will take 1-2 minutes.
echo.
pause
echo.
echo Stopping...
docker-compose down
echo.
echo Rebuilding (no cache)...
docker-compose build --no-cache
echo.
echo Starting...
docker-compose up -d
if %errorlevel% equ 0 (
    echo.
    echo OK Rebuild complete!
    echo Web: http://localhost:5000
) else (
    echo [ERROR] Rebuild failed
)
echo.
pause
goto menu

:logs
cls
echo ========================================
echo   LOGS (Ctrl+C to exit)
echo ========================================
echo.
docker-compose logs -f --tail=50
goto menu

:status
cls
echo ========================================
echo   CONTAINER STATUS
echo ========================================
echo.
docker-compose ps
echo.
echo ========================================
echo   RESOURCE USAGE
echo ========================================
echo.
docker stats --no-stream ekranchik-app
echo.
pause
goto menu

:web
cls
echo ========================================
echo   OPENING WEB INTERFACE
echo ========================================
echo.
echo Opening http://localhost:5000 ...
start http://localhost:5000
timeout /t 2 >nul
goto menu

:end
cls
echo Goodbye...
exit
