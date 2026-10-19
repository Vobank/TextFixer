@echo off
rem TextFixer: run in the background (tray icon). Installs everything it needs on first run.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" call "%~dp0Setup.bat" || exit /b 1
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0main.py"