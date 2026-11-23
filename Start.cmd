@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Bitte zuerst die Python-Umgebung nach README.md einrichten.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m bohr_atom view
if errorlevel 1 pause
