@echo off
cd /d %~dp0

set SCRIPT_NAME=launcher69.py
set ICON_PATH="data\icons\icon.ico"
set EXE_NAME=Launcher69.exe

pyinstaller --onefile --icon=%ICON_PATH% --noconsole %SCRIPT_NAME%

rd /s /q build
del /q launcher69.spec

echo Proceso de compilación terminado. El archivo .exe se encuentra en la carpeta dist.
pause