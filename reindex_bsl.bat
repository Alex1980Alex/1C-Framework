@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: BSL Full Reindex — 3 фазы индексации
::
:: Использование:
::   reindex_bsl.bat                         Индексация первого найденного проекта
::   reindex_bsl.bat "имя_проекта"           Индексация по имени проекта
::   reindex_bsl.bat --full --force          Полная принудительная индексация
::   reindex_bsl.bat --list                  Список проектов
::   reindex_bsl.bat --help                  Справка
::
:: Фазы:
::   1. FTS5 — SQLite полнотекстовый поиск (smart_index_bsl.py)
::   2. Qdrant — векторный поиск E5-large 1024d (reindex_bsl_qwen3.py)
::   3. Call Graph — граф вызовов SQLite (build_call_graph.py)
:: ============================================================

set FRAMEWORK=%~dp0
set FRAMEWORK=%FRAMEWORK:~0,-1%
set VENV=%FRAMEWORK%\.venv\Scripts\python.exe
set PROJECTS_ROOT=%FRAMEWORK%\src\projects\configuration

:: Скрипты
set FTS5_SCRIPT=%FRAMEWORK%\scripts\docs-mcp\smart_index_bsl.py
set QDRANT_SCRIPT=%FRAMEWORK%\scripts\reindex_bsl_qwen3.py
set CALLGRAPH_SCRIPT=%FRAMEWORK%\scripts\build_call_graph.py

:: Парсинг аргументов
set "PROJECT_NAME="
set "FULL_FLAG="
set "FORCE_FLAG="

:PARSE_ARGS
if "%~1"=="" goto :FIND_PROJECT
if "%~1"=="--help" goto :USAGE
if "%~1"=="-h" goto :USAGE
if "%~1"=="--list" goto :LIST
if "%~1"=="-l" goto :LIST
if "%~1"=="--full" (
    set "FULL_FLAG=--full"
    shift
    goto :PARSE_ARGS
)
if "%~1"=="--force" (
    set "FORCE_FLAG=--force"
    shift
    goto :PARSE_ARGS
)
:: Первый неизвестный аргумент = имя проекта
if "%PROJECT_NAME%"=="" (
    set "PROJECT_NAME=%~1"
)
shift
goto :PARSE_ARGS

:FIND_PROJECT
:: Определяем папку проекта
if not "%PROJECT_NAME%"=="" (
    :: По имени проекта
    set "PROJECT_DIR=%PROJECTS_ROOT%\%PROJECT_NAME%"
    if not exist "!PROJECT_DIR!" (
        echo [ERROR] Проект не найден: !PROJECT_DIR!
        echo Используйте --list для списка проектов.
        pause
        exit /b 1
    )
) else (
    :: Авто-поиск первого проекта с src/
    set "PROJECT_DIR="
    for /d %%D in ("%PROJECTS_ROOT%\*") do (
        if exist "%%D\src" (
            set "PROJECT_DIR=%%D"
        )
    )
    if "!PROJECT_DIR!"=="" (
        echo [ERROR] Нет проектов в %PROJECTS_ROOT%
        pause
        exit /b 1
    )
)

:: Извлекаем имя проекта для отображения
for %%I in ("%PROJECT_DIR%") do set "DISPLAY_NAME=%%~nxI"

echo.
echo ================================================================
echo   BSL Full Reindex — 3 фазы
echo ================================================================
echo.
echo   Проект:     %DISPLAY_NAME%
echo   Путь:       %PROJECT_DIR%
if not "%FULL_FLAG%"=="" echo   Режим:      Полная индексация
if not "%FORCE_FLAG%"=="" echo   Режим:      Принудительная переиндексация
echo.
echo   Фаза 1: FTS5 (SQLite полнотекстовый поиск)
echo   Фаза 2: Qdrant E5-large (1024d векторный поиск)
echo   Фаза 3: Call Graph (граф вызовов BSL)
echo.
echo ================================================================

set T0=%TIME%

:: ============================================================
:: Фаза 1: FTS5 — SQLite полнотекстовый индекс
:: ============================================================
echo.
echo ────────────────────────────────────────────────────────────
echo [1/3] FTS5 индексация (SQLite полнотекстовый поиск)
echo ────────────────────────────────────────────────────────────

if exist "%FTS5_SCRIPT%" (
    "%VENV%" "%FTS5_SCRIPT%" --path "%PROJECT_DIR%" --ast %FULL_FLAG% %FORCE_FLAG%
    if !ERRORLEVEL! EQU 0 (
        echo [OK] FTS5 индексация завершена
    ) else (
        echo [WARN] FTS5 индексация завершена с предупреждениями
    )
) else (
    echo [SKIP] Скрипт не найден: %FTS5_SCRIPT%
)

:: ============================================================
:: Фаза 2: Qdrant — векторный поиск E5-large
:: ============================================================
echo.
echo ────────────────────────────────────────────────────────────
echo [2/3] Qdrant индексация (E5-large, 1024d)
echo ────────────────────────────────────────────────────────────

if exist "%QDRANT_SCRIPT%" (
    "%VENV%" "%QDRANT_SCRIPT%" --project "%PROJECT_DIR%" --embedder e5 --batch-size 50
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Qdrant индексация завершена
    ) else (
        echo [WARN] Qdrant индексация завершена с предупреждениями
    )
) else (
    echo [SKIP] Скрипт не найден: %QDRANT_SCRIPT%
)

:: ============================================================
:: Фаза 3: Call Graph — граф вызовов BSL
:: ============================================================
echo.
echo ────────────────────────────────────────────────────────────
echo [3/3] Call Graph (граф вызовов BSL)
echo ────────────────────────────────────────────────────────────

if exist "%CALLGRAPH_SCRIPT%" (
    "%VENV%" "%CALLGRAPH_SCRIPT%" --project "%PROJECT_DIR%"
    if !ERRORLEVEL! EQU 0 (
        echo [OK] Call Graph построен
    ) else (
        echo [WARN] Call Graph завершен с предупреждениями
    )
) else (
    echo [SKIP] Скрипт не найден: %CALLGRAPH_SCRIPT%
)

:: ============================================================
:: Готово
:: ============================================================
echo.
echo ================================================================
echo [DONE] Индексация завершена!
echo.
echo   Доступный поиск:
echo     - BM25:       SQLite FTS5 (hybrid_search.db)
echo     - Векторный:  Qdrant bsl_code_v3 (E5-large, 1024d)
echo     - Call Graph:  cache\bsl_call_graph.db
echo     - Гибридный:  bsl_hybrid_search (BM25 + Vector + Call Graph)
echo ================================================================
echo.
pause
exit /b 0

:LIST
echo.
echo Доступные проекты:
echo ──────────────────
for /d %%D in ("%PROJECTS_ROOT%\*") do (
    if exist "%%D\src" (
        for %%I in ("%%D") do echo   %%~nxI
    )
)
echo.
exit /b 0

:USAGE
echo.
echo BSL Full Reindex — 3-фазная индексация для семантического поиска
echo.
echo Использование:
echo   reindex_bsl.bat                         Авто-поиск проекта
echo   reindex_bsl.bat "имя_проекта"           По имени проекта
echo   reindex_bsl.bat "имя_проекта" --full    Полная индексация
echo   reindex_bsl.bat "имя_проекта" --force   Принудительная переиндексация
echo   reindex_bsl.bat --list                  Список проектов
echo   reindex_bsl.bat --help                  Эта справка
echo.
echo Фазы:
echo   1. FTS5    — SQLite полнотекстовый поиск (smart_index_bsl.py --ast)
echo   2. Qdrant  — E5-large 1024d векторный поиск (reindex_bsl_qwen3.py --embedder e5)
echo   3. Graph   — граф вызовов BSL (build_call_graph.py)
echo.
echo Примеры:
echo   reindex_bsl.bat "260304_GKSTCPLK-2182"
echo   reindex_bsl.bat "260304_GKSTCPLK-2182" --full --force
echo   reindex_bsl.bat --list
echo.
exit /b 0
