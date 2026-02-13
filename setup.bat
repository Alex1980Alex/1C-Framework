@echo off
REM Full portable setup script for Windows
REM Creates venv and installs all dependencies
REM Usage: setup.bat
echo ============================================
echo  PDF Vector ^& Graph Framework - Setup
echo ============================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Install Python 3.11+
    exit /b 1
)
echo [OK] Python found

REM Check uv
uv --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] uv found, using uv for fast install
    set "USE_UV=1"
) else (
    echo [INFO] uv not found, using pip
    set "USE_UV=0"
)

REM Create venv
if not exist ".venv" (
    echo [STEP] Creating virtual environment...
    if "%USE_UV%"=="1" (
        uv venv .venv
    ) else (
        python -m venv .venv
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Activate
call .venv\Scripts\activate.bat

REM Install
echo [STEP] Installing dependencies...
if "%USE_UV%"=="1" (
    uv pip install -e ".[dev]"
) else (
    pip install -e ".[dev]"
)

echo.
echo ============================================
echo  Setup complete!
echo  Activate: activate.bat
echo  Run:      run.bat python -c "import src"
echo ============================================
