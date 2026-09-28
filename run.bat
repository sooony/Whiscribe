@echo off
title Dyktowanie AI - Whisper RTX 3060
cd /d "%~dp0"

echo =======================================================
echo          DYKTOWANIE MOWY AI (WHISPER TURBO)
echo          NVIDIA GeForce RTX 3060 (12GB)
echo =======================================================
echo.
echo Domyslny skrot klawiszowy: Ctrl + Alt + D
echo (Mozesz go przypisac do myszki MX Master w Logi Options+)
echo.
echo Uruchamianie aplikacji w tle...
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
.\venv\Scripts\python.exe app.py
pause
