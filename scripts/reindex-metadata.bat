@echo off
chcp 65001 >nul
setlocal
:: Reindex 1C metadata to Qdrant (incremental by default)
:: Usage: reindex-metadata.bat [--full] [--dry-run] [--format md|csv|qdrant]

set SCRIPT_DIR=%~dp0
set VENV=%SCRIPT_DIR%..\\.venv\\Scripts\\python.exe

if not exist "%VENV%" (
    echo ERROR: .venv not found. Run: python -m venv .venv
    exit /b 1
)

echo === Reindex 1C Metadata ===
"%VENV%" "%SCRIPT_DIR%reindex_metadata.py" %*
