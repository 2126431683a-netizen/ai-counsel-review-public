@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Python environment missing. Please install the Windows EXE package or follow README.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "desktop\start_web.py"
