@echo off
chcp 65001 >nul
echo.
echo ========================================
echo FTP FILE READER TEST
echo ========================================
echo.

if "%~1"=="" (
    echo Usage: ftp_test.bat [host] [path] [user] [pass] [port]
    echo.
    echo Examples:
    echo   ftp_test.bat 192.168.1.100 /logs/data.txt
    echo   ftp_test.bat 192.168.1.100 /logs/data.txt admin password
    echo   ftp_test.bat 192.168.1.100 /logs/data.txt admin password 21
    echo.
    echo Or run without parameters for interactive mode
    echo.
)

python ftp_test.py %*

echo.
pause
