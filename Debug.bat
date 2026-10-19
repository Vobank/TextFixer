@echo off
rem TextFixer with a console window: shows logs and errors (for troubleshooting)
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call "%~dp0Setup.bat" || exit /b 1
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
pause