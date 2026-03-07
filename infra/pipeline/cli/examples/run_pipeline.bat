@echo off
REM Pipeline CLI - Batch Script Example
REM
REM Использование:
REM   run_pipeline.bat <project> "<task>"
REM
REM Примеры:
REM   run_pipeline.bat GKSTCPLK-1872 "Добавить валидацию"
REM   run_pipeline.bat GKSTCPLK-1996 "Исправить ошибку"
REM
REM Версия: 1.0.0
REM Дата: 2025-12-23

setlocal EnableDelayedExpansion

REM Проверка аргументов
if "%~1"=="" (
    echo Usage: run_pipeline.bat ^<project^> "^<task^>"
    echo.
    echo Examples:
    echo   run_pipeline.bat GKSTCPLK-1872 "Добавить валидацию"
    exit /b 1
)

if "%~2"=="" (
    echo Error: Task description is required
    echo Usage: run_pipeline.bat ^<project^> "^<task^>"
    exit /b 1
)

set PROJECT=%~1
set TASK=%~2

echo ============================================================
echo Pipeline CLI Runner
echo ============================================================
echo.
echo Project: %PROJECT%
echo Task: %TASK%
echo.

REM Переходим в корень проекта
cd /d %~dp0..\..\..\..

REM Проверяем наличие Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found
    exit /b 1
)

REM Показываем статус перед запуском
echo [1/4] Checking current status...
python -m shared.pipeline.cli status
echo.

REM Показываем конфигурацию
echo [2/4] Checking configuration...
python -m shared.pipeline.cli config show
echo.

REM Запускаем pipeline
echo [3/4] Starting pipeline...
echo.
python -m shared.pipeline.cli run --project "%PROJECT%" --task "%TASK%"
set RUN_RESULT=%ERRORLEVEL%
echo.

REM Показываем результат
echo [4/4] Checking result...
python -m shared.pipeline.cli status
echo.

echo ============================================================
if %RUN_RESULT%==0 (
    echo [SUCCESS] Pipeline completed successfully
) else (
    echo [FAILED] Pipeline failed with exit code: %RUN_RESULT%
)
echo ============================================================

exit /b %RUN_RESULT%
