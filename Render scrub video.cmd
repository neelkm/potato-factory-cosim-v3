@echo off
setlocal
cd /d "%~dp0"
".venv_physx\Scripts\python.exe" src\render_scrub_video.py --spp 16 --workers 1 %*
if errorlevel 1 pause
