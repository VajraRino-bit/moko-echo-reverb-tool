@echo off
setlocal
cd /d "%~dp0"
set "TEMP=%~dp0tmp"
set "TMP=%TEMP%"
set "GRADIO_TEMP_DIR=%~dp0tmp\gradio"
set "GRADIO_ANALYTICS_ENABLED=False"
set "HF_HUB_OFFLINE=1"
if not exist ".venv\Scripts\python.exe" (
  echo Please run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 app.py
if errorlevel 1 pause
