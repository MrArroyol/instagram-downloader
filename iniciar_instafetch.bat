@echo off
title InstaFetch - Descargador de Videos de Instagram
echo ========================================================
echo   Iniciando InstaFetch en http://127.0.0.1:5000
echo ========================================================
start "" "http://127.0.0.1:5000"
py "%~dp0app.py"
pause
