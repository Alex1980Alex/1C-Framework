@echo off
REM Portable activation script for Windows
REM Usage: activate.bat
set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
echo [OK] Virtual environment activated
echo Python:
python --version
echo Project: %SCRIPT_DIR%
