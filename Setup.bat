@echo off
rem TextFixer: install dependencies into the .venv folder (once)
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo  Python was not found. Install Python 3.10+ from https://www.python.org/downloads/
  echo  ^(tick "Add python.exe to PATH" in the installer^) and run this again.
  echo.
  pause
  exit /b 1
)
echo  Setting up TextFixer ^(one time, about a minute^)...
%PY% -m venv .venv || (echo Could not create .venv & pause & exit /b 1)
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || (echo Could not install dependencies & pause & exit /b 1)
echo  Done.
exit /b 0