@echo off
cd /d "%~dp0"
".venv_physx\Scripts\python.exe" src\render_video.py --spp 16 --workers 3 %*
if errorlevel 1 pause
