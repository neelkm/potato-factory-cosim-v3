@echo off
cd /d "%~dp0"
".venv_physx\Scripts\python.exe" src\capture_physics_debug.py
if errorlevel 1 exit /b 1
".venv_physx\Scripts\python.exe" src\prepare_debug_view.py
if errorlevel 1 exit /b 1
".venv_physx\Scripts\python.exe" scripts\validate_debug_capture.py
if errorlevel 1 exit /b 1
echo Debug capture is ready. Open Launch Physics Debug.cmd.
