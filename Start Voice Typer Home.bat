@echo off
rem Home PC only: lets your other computers use this computer's graphics card (Reglages > PC a la maison).
rem Starts Voice Typer Home next to the clock (blue icon). Never run this on the work PC. Guide: docs\HOME.md
rem   --console : old mode, in this window (shows every line)    --new-key : make a new key
cd /d "%~dp0"
if /i "%~1"=="--console" (
  title Voice Typer Home
  "%~dp0venv\Scripts\python.exe" -m home_server --port 8765
  pause
  exit /b
)
if /i "%~1"=="--new-key" (
  "%~dp0venv\Scripts\python.exe" -m home_server --new-key --only-key
  pause
  exit /b
)
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0run_home.pyw"
