@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launch-SCORM.ps1"
if errorlevel 1 (
  echo.
  echo The studio did not start.
  pause
)
