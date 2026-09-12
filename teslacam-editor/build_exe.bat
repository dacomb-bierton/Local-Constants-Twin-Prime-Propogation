@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call run.bat --help >nul
".venv\Scripts\python.exe" -m pip install pyinstaller || exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm teslacam_editor.spec || exit /b 1
echo.
echo Built dist\TeslaCamEditor\TeslaCamEditor.exe  (copy the whole dist\TeslaCamEditor folder)
pause
