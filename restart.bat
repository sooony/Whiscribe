@echo off
title Restart Dyktowanie AI
cd /d "%~dp0"
echo Zamykanie poprzednich procesow...
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
ping 127.0.0.1 -n 2 >nul
echo Uruchamianie aplikacji w tle...
wscript.exe run_silent.vbs
echo Aplikacja uruchomiona pomyslnie!
ping 127.0.0.1 -n 2 >nul
