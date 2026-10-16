@echo off
rem Запуск с консолью — видно логи и ошибки (для проверки)
chcp 65001 >nul
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
pause
