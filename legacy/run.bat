@echo off
cd /d "%~dp0"
start "" "http://localhost:8420/?bare=1"
.venv\Scripts\python.exe listener.py
pause
