@echo off
chcp 65001
cd /d "%~dp0"
echo ════════════════════════════════════════════════════════════════
echo       WEB ADMINKA - ZAPUSK
echo ════════════════════════════════════════════════════════════════
echo.
echo Otkryvaetsya veb-interfeys na http://localhost:5000
echo.
echo Redaktiruyte Excel, sohranyayte - vse obnovitsya!
echo Dlya vyhoda nazhmite Ctrl+C
echo.
echo Zapusk Flask servera...
echo.
timeout /t 3 /nobreak > nul
start http://localhost:5000
python app.py
pause
