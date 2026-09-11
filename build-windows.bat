@echo off
cd /d "%~dp0"
py -3 -m venv .venv-build
if errorlevel 1 exit /b 1
.venv-build\Scripts\python.exe -m pip install -r packaging\requirements-windows.txt
if errorlevel 1 exit /b 1
.venv-build\Scripts\python.exe packaging\build.py exe
if errorlevel 1 exit /b 1
echo EXE is in dist\NelsonictRouterManager.exe
pause
