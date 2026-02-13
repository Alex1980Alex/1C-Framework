@echo off
REM Portable runner - activates venv and runs command
REM Usage: run.bat <command> [args...]
REM Example: run.bat python -m pytest
REM Example: run.bat pdf-framework --help
set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"
%*
