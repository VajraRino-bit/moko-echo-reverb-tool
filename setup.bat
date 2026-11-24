@echo off
setlocal
cd /d "%~dp0"
set "TEMP=%~dp0tmp"
set "TMP=%TEMP%"
set "PIP_CACHE_DIR=%~dp0cache"
if not exist "tmp" mkdir "tmp"
if not exist ".venv\Scripts\python.exe" (
  py -3.10 -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -c "import pedalboard,soundfile,gradio,numpy; from pedalboard import BrickwallLimiter"
if errorlevel 1 goto fail
echo Setup complete. Run run_tool.bat.
pause
exit /b 0
:fail
echo Setup failed. Please check the error above.
pause
exit /b 1
