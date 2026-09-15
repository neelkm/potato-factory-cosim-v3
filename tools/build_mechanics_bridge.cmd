@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cd /d "%~dp0.."
cl /nologo /LD /O2 /MD /DNDEBUG /Itools\physx_include src\mechanics_bridge.cpp /Fo:tools\mechanics_bridge.obj /link /OUT:tools\mechanics_bridge.dll
