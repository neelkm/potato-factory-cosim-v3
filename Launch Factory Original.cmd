@echo off
cd /d "%~dp0"
".venv_physx\Scripts\python.exe" app.py --source factory_replay.usdc --cache cache
if errorlevel 1 pause
