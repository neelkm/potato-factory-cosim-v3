@echo off
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
cd /d "%~dp0"
cl /nologo /LD /O2 /MT /EHsc FactoryController.cpp /link /OUT:FactoryController.dll
