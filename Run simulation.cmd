@echo off
cd /d "%~dp0"
".venv_coordinator\Scripts\python.exe" scripts\run_factory.py %*
if errorlevel 1 pause
