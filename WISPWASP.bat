@echo off
REM Starts WispWasp from source, for development.
REM The installed build is started from its own shortcut instead.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: no virtual environment found at .venv
  echo Create one and install from requirements-lock.txt first.
  pause
  exit /b 1
)

start "" ".venv\Scripts\python.exe" app.py %*
