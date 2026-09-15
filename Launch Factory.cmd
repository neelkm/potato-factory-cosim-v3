@echo off
cd /d "%~dp0"
".venv_physx\Scripts\python.exe" app.py %*
if errorlevel 1 pause
