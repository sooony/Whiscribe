@echo off
title Whiscribe - Whisper Voice Typing AI
cd /d "%~dp0"

echo =======================================================
echo          WHISCRIBE - AI VOICE TYPING (WHISPER TURBO)
echo          NVIDIA GeForce RTX 3060 (12GB)
echo =======================================================
echo.
echo Domyslny skrot klawiszowy: Ctrl + Alt + D
echo (Mozesz go przypisac do myszki MX Master w Logi Options+)
echo.
echo Uruchamianie Whiscribe...
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
.\venv\Scripts\python.exe app.py
pause
