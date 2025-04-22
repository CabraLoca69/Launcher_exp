@echo off
rem Cambia al directorio donde está el script principal de Python (si no es el mismo que el .bat)
cd /d %~dp0

rem Nombre del script de Python a compilar
set SCRIPT_NAME=launcher69.py

rem Ruta del icono
set ICON_PATH=icons\icon.ico

rem Nombre del archivo ejecutable de salida
set EXE_NAME=Launcher69.exe

rem Usamos PyInstaller para crear el .exe con el icono
pyinstaller --onefile --icon=%ICON_PATH% --noconsole %SCRIPT_NAME%

rem Limpiar archivos temporales generados por PyInstaller
rd /s /q build
del /q mi_script.spec

echo Proceso de compilación terminado. El archivo .exe se encuentra en la carpeta dist.
pause