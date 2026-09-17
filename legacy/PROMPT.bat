@echo off
title Manual image prompt
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-prompt.ps1"
