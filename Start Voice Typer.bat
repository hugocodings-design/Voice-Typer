@echo off
rem Double-click to open Voice Typer without a console window.
cd /d "%~dp0"
start "" "%~dp0venv\Scripts\pythonw.exe" -m voice_typer
