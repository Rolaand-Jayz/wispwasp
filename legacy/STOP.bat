@echo off
REM Stops the listener and ComfyUI.
echo Stopping listener and ComfyUI...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*listener.py*' -or $_.CommandLine -like '*ComfyUI*main.py*' } | ForEach-Object { Write-Host ('  stopped ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }"
echo Done.
timeout /t 3 >nul
