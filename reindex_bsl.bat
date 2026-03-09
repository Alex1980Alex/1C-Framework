@echo off
chcp 65001 >nul
echo ============================================
echo   BSL Reindex - E5-large (1024d)
echo ============================================
echo.

set VENV=%~dp0.venv\Scripts\python.exe
set SCRIPT=%~dp0scripts\reindex_bsl_qwen3.py
set PROJECT=%~dp0src\projects\configuration

:: Find first EDT project with src/ subfolder
set FOUND=
for /d %%D in ("%PROJECT%\*") do (
    if exist "%%D\src" (
        set FOUND=%%D
    )
)

if "%FOUND%"=="" (
    echo ERROR: No EDT project found in %PROJECT%
    echo Expected: src\projects\configuration\{project}\src\
    pause
    exit /b 1
)

echo Project: %FOUND%
echo Embedder: E5-large (1024d, ~15 min)
echo Collection: bsl_code_v3
echo.

"%VENV%" "%SCRIPT%" --project "%FOUND%" --embedder e5 --batch-size 50

echo.
echo Done!
pause
