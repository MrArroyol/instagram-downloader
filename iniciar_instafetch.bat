@echo off
title InstaFetch - Descargador de Videos de Instagram y TikTok
echo ================================================================
echo   Iniciando InstaFetch (Instagram y TikTok) en http://127.0.0.1:5000
echo ================================================================
start "" "http://127.0.0.1:5000"
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" "%~dp0app.py"
) else (
    py "%~dp0app.py"
)
pause
