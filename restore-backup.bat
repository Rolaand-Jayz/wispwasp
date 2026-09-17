@echo off
REM Restores the working files from the last known-good snapshot.
REM Your generated images in output\ and on the Desktop are not touched,
REM and neither are the two .venv folders or your ComfyUI models.
cd /d "%~dp0"

set SNAP=backup\2026-09-15-v0.1.1

if not exist "%SNAP%\app.py" (
  echo ERROR: snapshot not found at %SNAP%
  pause
  exit /b 1
)

echo Restoring from %SNAP% ...

for %%F in (
  app.py selftest.py demo_stubs.py overlay.html
  settings.json SETUP.md requirements-lock.txt
  wispwasp.spec installer.iss build.ps1 WISPWASP.bat
  test_core2.py test_engine.py test_layouts.py test_server.py
  test_wav.py test_setup.py test_install.py test_mic.py test_process_audio.py test_clear.py test_catalog.py test_recovery.py test_activation.py test_options.py test_sync.py test_favourites.py test_confirm.py test_customize.py test_docs.py
  test_real_audio.py test_live_download.py test_full_install.py
) do (
  if exist "%SNAP%\%%F" copy /Y "%SNAP%\%%F" "%%F" >nul && echo   %%F
)

REM Whole folders, not a file list. Stale .py files left behind would
REM shadow restored ones, so each is cleared first. hooks\ matters as much
REM as the rest: without the PyAV stub the packaged build will not start.
for %%D in (avcore avgui hooks) do (
  if exist "%SNAP%\%%D" (
    if exist "%%D" del /Q "%%D\*.py" >nul 2>&1
    if not exist "%%D" mkdir "%%D"
    copy /Y "%SNAP%\%%D\*.py" "%%D\" >nul && echo   %%D\
  )
)

REM tools\7zr.exe unpacks the ComfyUI download. Without it setup fails at
REM the extract step, which is after a 1.8 GB download - so it matters as
REM much as any source file.
if exist "%SNAP%\tools\7zr.exe" (
  if not exist "tools" mkdir "tools"
  copy /Y "%SNAP%\tools\7zr.exe" "tools\" >nul && echo   tools\7zr.exe
)

REM Branding. The app falls back to a text label if the logo is missing,
REM so this is not fatal, but the icon comes from here too.
if exist "%SNAP%\assets" (
  if not exist "assets" mkdir "assets"
  copy /Y "%SNAP%\assets\*" "assets\" >nul 2>&1 && echo   assets\
)

if exist "%SNAP%\installer\LICENSE-NOTICE.txt" (
  if not exist "installer" mkdir "installer"
  copy /Y "%SNAP%\installer\LICENSE-NOTICE.txt" "installer\" >nul && echo   installer\
)

if exist "%SNAP%\legacy" (
  if not exist "legacy" mkdir "legacy"
  copy /Y "%SNAP%\legacy\*" "legacy\" >nul 2>&1 && echo   legacy\
)

REM Python caches bytecode, and a stale __pycache__ can resurrect a module
REM that was just deleted.
for /d /r %%C in (__pycache__) do @if exist "%%C" rd /s /q "%%C" 2>nul

echo.
echo Done. Start the app with WISPWASP.bat, or rebuild with build.ps1
pause
