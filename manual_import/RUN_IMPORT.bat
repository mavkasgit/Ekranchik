@echo off
chcp 65001 > nul
cd /d "%~dp0.."

echo.
echo ============================================
echo   Loading profiles into database
echo ============================================
echo.

if not exist "manual_import\profiles_anod.csv" (
    echo ERROR: profiles_anod.csv not found!
    goto error
)

if not exist "manual_import\load_profiles.py" (
    echo ERROR: load_profiles.py not found!
    goto error
)

echo OK: Files found
echo.

python manual_import\load_profiles.py manual_import\profiles_anod.csv

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo SUCCESS! Profiles loaded into database!
    echo ============================================
    timeout /t 3 /nobreak
    exit /b 0
) else (
    echo.
    echo ============================================
    echo ERROR! Something went wrong!
    echo ============================================
    pause
    exit /b 1
)
