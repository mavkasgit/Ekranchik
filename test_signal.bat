@echo off
echo Type 'q' to quit
echo.

:loop
set /p HANGER="Hanger: "

if "%HANGER%"=="q" goto end
if "%HANGER%"=="Q" goto end

for /f "tokens=1-2 delims=:" %%a in ("%TIME%") do set CURRENT_TIME=%%a:%%b

curl -s -X POST http://localhost:5000/api/signal -H "Content-Type: application/json" -d "{\"hanger_number\": \"%HANGER%\", \"exit_time\": \"%CURRENT_TIME%\"}" >nul

echo OK: %HANGER% [%CURRENT_TIME%]
echo.
goto loop

:end
echo Bye!
