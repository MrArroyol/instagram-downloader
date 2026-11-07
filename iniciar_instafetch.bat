@echo off
title InstaFetch - Descargador de Videos de Instagram y TikTok
echo ================================================================
echo   Iniciando InstaFetch (Instagram y TikTok) en http://127.0.0.1:5000
echo ================================================================

REM Cerrar instancia previa en el puerto 5000 si existe para cargar siempre la ultima version
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

start "" "http://127.0.0.1:5000"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%~dp0app.py"
) else (
    py "%~dp0app.py"
)
pause
