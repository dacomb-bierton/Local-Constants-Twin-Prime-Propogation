@echo off
setlocal
cd /d "%~dp0"
title TeslaCam Editor

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.10 or newer was not found.
  echo Install it from https://www.python.org/downloads/windows/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PY% -m venv .venv || (echo Could not create the virtual environment. & pause & exit /b 1)
  echo Installing dependencies ^(first run only, this includes a bundled ffmpeg^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo Dependency installation failed. & pause & exit /b 1)
)

echo Starting TeslaCam Editor... close this window to stop it.
".venv\Scripts\python.exe" -m teslacam_editor %*
if errorlevel 1 pause
