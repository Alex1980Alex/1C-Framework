@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: Индексация фреймворка D:\1С-Framework
:: Multi-Language: BSL, JavaScript, TypeScript, Python, Markdown
:: РЕКУРСИВНО с корня, ИСКЛЮЧАЯ src/projects/configuration/
:: ============================================================

set FRAMEWORK_ROOT=D:\1С-Framework
set SCRIPT_DIR=%~dp0

:: Создаём папку logs если не существует
if not exist "%FRAMEWORK_ROOT%\logs" mkdir "%FRAMEWORK_ROOT%\logs"

:: Парсинг аргументов
set "FORCE_INDEX=0"
set "FULL_INDEX=0"
set "LANGUAGES=bsl,javascript,python,markdown"

if "%~1"=="--help" goto :USAGE
if "%~1"=="-h" goto :USAGE
if "%~1"=="--force" set "FORCE_INDEX=1"
if "%~1"=="--full" set "FULL_INDEX=1"
if "%~1"=="--languages" set "LANGUAGES=%~2"
if "%~2"=="--force" set "FORCE_INDEX=1"
if "%~2"=="--full" set "FULL_INDEX=1"
if "%~2"=="--languages" set "LANGUAGES=%~3"
if "%~3"=="--force" set "FORCE_INDEX=1"
if "%~3"=="--full" set "FULL_INDEX=1"
if "%~3"=="--languages" set "LANGUAGES=%~4"
if "%~4"=="--languages" set "LANGUAGES=%~5"

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║    MULTI-LANGUAGE ИНДЕКСАЦИЯ ФРЕЙМВОРКА                  ║
echo ║    D:\1С-Framework (рекурсивно)                          ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo [ROOT] %FRAMEWORK_ROOT%
echo [LANG] Языки: %LANGUAGES%
if "%FORCE_INDEX%"=="1" echo [FORCE] Принудительная переиндексация
if "%FULL_INDEX%"=="1" echo [FULL]  Полная индексация
echo.

echo ────────────────────────────────────────────────────────────
echo Индексация с КОРНЯ фреймворка рекурсивно
echo ────────────────────────────────────────────────────────────
echo   Корень: %FRAMEWORK_ROOT%
echo.
echo АВТОМАТИЧЕСКИ ИСКЛЮЧЕНО:
echo   - src/projects/configuration/ (отдельные проекты)
echo   - node_modules/, dist/, build/, __pycache__/
echo   - .venv/, venv/, .git/
echo ────────────────────────────────────────────────────────────
echo.

:: Остановка MCP сервера (освобождаем БД)
echo [MCP] Остановка MCP серверов...
wmic process where "commandline like '%%mcp_server.py%%'" delete >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] MCP серверы остановлены
echo.

:: ============================================================
:: Единый вызов индексации с корня фреймворка
:: ============================================================

set "FORCE_FLAG="
set "FULL_FLAG="
if "%FORCE_INDEX%"=="1" set "FORCE_FLAG=--force"
if "%FULL_INDEX%"=="1" set "FULL_FLAG=--full"

echo [INDEX] Запуск индексации фреймворка...
echo.
python "%SCRIPT_DIR%docs-mcp\smart_index_bsl.py" --framework --languages "%LANGUAGES%" %FORCE_FLAG% %FULL_FLAG%

if !ERRORLEVEL! EQU 0 (
    echo.
    echo [OK] Индексация фреймворка завершена успешно
) else (
    echo.
    echo [WARN] Индексация завершена с предупреждениями
)

:: ============================================================
:: Готово
:: ============================================================
echo.
echo ════════════════════════════════════════════════════════════
echo [DONE] Индексация фреймворка завершена!
echo.
echo Проиндексировано (рекурсивно с корня):
echo   - docs/ (документация)
echo   - .claude/ (skills, hooks, agents)
echo   - scripts/ (Python, bat)
echo   - src/bsl/ (BSL инфраструктура)
echo   - tools/ (MCP серверы)
echo.
echo НЕ проиндексировано (используйте index-folder.bat):
echo   - src/projects/configuration/* (отдельные проекты)
echo.
echo Доступен поиск:
echo   mcp__bsl-semantic-search__bsl_search("запрос")
echo ════════════════════════════════════════════════════════════
goto :END

:USAGE
echo.
echo Использование:
echo   index-framework.bat                          Индексация фреймворка (smart mode)
echo   index-framework.bat --languages bsl,js,py    Указать языки
echo   index-framework.bat --full                   Полная индексация
echo   index-framework.bat --force                  Принудительная переиндексация
echo   index-framework.bat --full --force
echo.
goto :END

:END
endlocal
