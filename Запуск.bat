@echo off
rem Тихий запуск без окна консоли (работает в фоне, иконка в трее)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"
