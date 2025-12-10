@echo off
setlocal enabledelayedexpansion

:menu
cls
echo.
echo ========================================
echo MAIN MENU - Log Processing System
echo ========================================
echo.
echo Select action:
echo.
echo 1. Test FTP connection
echo    - Check FTP server availability
echo    - Show file list in directory
echo    - Perform 10 diagnostic checks
echo    - Use for connection diagnostics
echo.
echo 2. Read today log from FTP
echo    - Load full log for today
echo    - Show file content (first 30 lines)
echo    - Use to view all events for the day
echo.
echo 3. Parse logs and send signals (full file)
echo    - Read entire log from FTP
echo    - Find all hanger unload events
echo    - Send signals to app.py
echo    - Use for initial log processing
echo    - Warning: reads entire file, may be slow
echo.
echo 4. Parse only new lines (RECOMMENDED)
echo    - Read only added lines
echo    - Save position in file (state.json)
echo    - Save traffic and time
echo    - Use for regular runs (every minute)
echo.
echo 5. Auto-run parser every minute
echo    - Run parser in loop every 60 seconds
echo    - Use incremental mode (only new lines)
echo    - Use for continuous monitoring
echo    - Press Ctrl+C to stop
echo.
echo 0. Exit
echo.
set /p choice="Enter number (0-5): "

if "%choice%"=="1" goto test_ftp
if "%choice%"=="2" goto read_today
if "%choice%"=="3" goto parse_full
if "%choice%"=="4" goto parse_incremental
if "%choice%"=="5" goto auto_run
if "%choice%"=="0" goto exit_app

echo.
echo Error: invalid choice
timeout /t 2 >nul
goto menu

REM ========================================
REM 1. TEST FTP CONNECTION
REM ========================================
:test_ftp
cls
echo.
echo ========================================
echo 1. TEST FTP CONNECTION
echo ========================================
echo.
echo Description:
echo - Check FTP server availability
echo - Connect with credentials
echo - Show file list in directory
echo - Perform 10 diagnostic checks
echo.
echo Parameters:
echo   Host: 172.17.11.194
echo   Port: 21
echo   User: omron
echo   Pass: 12345678
echo   Path: /MEMCARD1/messages/
echo.
echo Use for:
echo - Testing FTP connection
echo - Network diagnostics
echo - Viewing available files
echo.
echo Running script...
echo.
python scripts/ftp_test.py
echo.
pause
goto menu

REM ========================================
REM 2. READ TODAY LOG
REM ========================================
:read_today
cls
echo.
echo ========================================
echo 2. READ TODAY LOG FROM FTP
echo ========================================
echo.
echo Description:
echo - Load full log for today
echo - Show first 30 lines of content
echo - Perform 10 checks while reading
echo.
echo Use for:
echo - Viewing all events for the day
echo - Checking log content
echo - Diagnostics
echo.
echo Running script...
echo.
python scripts/ftp_reader.py
echo.
pause
goto menu

REM ========================================
REM 3. PARSE FULL LOG
REM ========================================
:parse_full
cls
echo.
echo ========================================
echo 3. PARSE LOGS AND SEND SIGNALS
echo ========================================
echo.
echo Description:
echo - Read entire log for today from FTP
echo - Find all hanger unload events
echo - Send signals to app.py
echo - Show status for each event
echo.
echo What it looks for:
echo   Pattern: "Razgruzka podvesa - X v poz. 34"
echo   This is the moment when hanger exits the line
echo.
echo Use for:
echo - Initial log processing
echo - Syncing app.py with logs
echo - Sending all events for the day
echo.
echo Warning: reads entire file, may be slow
echo.
echo Running script...
echo.
python scripts/log_parser.py
echo.
pause
goto menu

REM ========================================
REM 4. PARSE ONLY NEW LINES
REM ========================================
:parse_incremental
cls
echo.
echo ========================================
echo 4. PARSE ONLY NEW LINES (RECOMMENDED)
echo ========================================
echo.
echo Description:
echo - Read only added lines
echo - Save position in file (log_parser_state.json)
echo - Save traffic and time
echo - Ideal for frequent runs
echo.
echo How it works:
echo 1. Save file position (byte offset)
echo 2. On next run read only from that position
echo 3. Parse only new events
echo 4. Send signals to app.py
echo 5. Update position
echo.
echo Use for:
echo - Regular runs (every minute)
echo - Minimizing FTP traffic
echo - Continuous monitoring
echo.
echo Recommended: run every minute!
echo.
echo Running script...
echo.
python scripts/log_parser_incremental.py
echo.
pause
goto menu

REM ========================================
REM 5. AUTO-RUN EVERY MINUTE
REM ========================================
:auto_run
cls
echo.
echo ========================================
echo 5. AUTO-RUN PARSER EVERY MINUTE
echo ========================================
echo.
echo Description:
echo - Run parser in loop
echo - Interval: 60 seconds
echo - Use incremental mode (only new lines)
echo - Save traffic and resources
echo.
echo How to stop:
echo - Press Ctrl+C
echo - Enter Y and press Enter
echo.
echo Use for:
echo - Continuous monitoring
echo - Automatic synchronization
echo - Background process
echo.
echo Starting...
echo.

:auto_loop
echo [%date% %time%] Running parser...
python scripts/log_parser_incremental.py
echo.
echo Waiting 60 seconds until next run...
timeout /t 60 /nobreak
goto auto_loop

REM ========================================
REM EXIT
REM ========================================
:exit_app
cls
echo.
echo Goodbye!
echo.
exit /b 0
