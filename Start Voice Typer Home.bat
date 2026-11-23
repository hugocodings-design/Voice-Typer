@echo off
rem Home PC only: lets your work PC use this computer's graphics card (Réglages → PC à la maison).
rem Never run this on the work PC. Guide: docs\HOME.md
title Voice Typer Home
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -m home_server %*
pause
