@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: ============================================================
:: Multi-Language индексация для семантического поиска
:: Поддержка: BSL, JavaScript, TypeScript, Python, Markdown
:: Использование:
::   index-folder.bat "путь\к\папке"           Индексация по пути
::   index-folder.bat "имя_проекта"            Индексация по имени проекта
::   index-folder.bat --list                   Список проектов
::   index-folder.bat "путь" --docs-only       Только 1c-docs-rag
::   index-folder.bat "путь" --bsl-only        Только bsl-semantic-search
::   index-folder.bat "путь" --full            Полная индексация (все файлы)
::   index-folder.bat "путь" --force           Принудительная переиндексация
::   index-folder.bat "путь" --languages js,py Указать языки
::   index-folder.bat --help                   Справка
:: ============================================================

set SCRIPT_DIR=%~dp0
set FRAMEWORK_ROOT=D:\1С-Framework

:: Создаём папку logs если не существует
if not exist "%FRAMEWORK_ROOT%\logs" mkdir "%FRAMEWORK_ROOT%\logs"
set PROJECTS_ROOT=%FRAMEWORK_ROOT%\src\projects\configuration
set SMART_SCRIPT=%SCRIPT_DIR%docs-mcp\smart_index_bsl.py

:: Проверка аргументов
if "%~1"=="" goto :USAGE
if "%~1"=="--help" goto :USAGE
if "%~1"=="-h" goto :USAGE
if "%~1"=="--list" goto :LIST
if "%~1"=="-l" goto :LIST

:: Парсинг аргументов
set "INPUT=%~1"
set "MODE=both"
set "BACKGROUND=0"
set "FULL_INDEX=0"
set "FORCE_INDEX=0"
set "LANGUAGES=bsl,javascript,python,markdown"
set "EXIT_CODE=0"

if "%~2"=="--docs-only" set "MODE=docs"
if "%~2"=="--bsl-only" set "MODE=bsl"
if "%~2"=="--background" set "BACKGROUND=1"
if "%~2"=="--full" set "FULL_INDEX=1"
if "%~2"=="--force" set "FORCE_INDEX=1"
if "%~2"=="--languages" set "LANGUAGES=%~3"
if "%~3"=="--background" set "BACKGROUND=1"
if "%~3"=="--full" set "FULL_INDEX=1"
if "%~3"=="--force" set "FORCE_INDEX=1"
if "%~3"=="--languages" set "LANGUAGES=%~4"
if "%~4"=="--full" set "FULL_INDEX=1"
if "%~4"=="--force" set "FORCE_INDEX=1"
if "%~4"=="--languages" set "LANGUAGES=%~5"
if "%~5"=="--force" set "FORCE_INDEX=1"
if "%~5"=="--languages" set "LANGUAGES=%~6"
if "%~6"=="--languages" set "LANGUAGES=%~7"

:: Определяем: путь или имя проекта?
:: Проверяем букву диска (X:) или UNC-путь (\\) — findstr через pipe ломается на кириллице
set "IS_PATH=0"
if "!INPUT:~1,1!"==":" set "IS_PATH=1"
if "!INPUT:~0,2!"=="\\" set "IS_PATH=1"
if "!IS_PATH!"=="1" (
    set "FOLDER_PATH=%INPUT%"
) else (
    :: Это имя проекта — ищем в projects/configuration
    set "FOLDER_PATH=%PROJECTS_ROOT%\%INPUT%\src"
    if not exist "!FOLDER_PATH!" (
        set "FOLDER_PATH=%PROJECTS_ROOT%\%INPUT%"
    )
)

:: Проверка существования папки
if not exist "%FOLDER_PATH%" (
    echo [ERROR] Папка не найдена: %FOLDER_PATH%
    echo.
    echo Возможно вы имели в виду проект? Используйте --list для списка.
    goto :USAGE
)

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║      MULTI-LANGUAGE ИНДЕКСАЦИЯ СЕМАНТИЧЕСКОГО ПОИСКА    ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo [INPUT]  Папка: %FOLDER_PATH%
echo [LANG]   Языки: %LANGUAGES%
echo [MODE]   Режим: %MODE%
if "%FULL_INDEX%"=="1" echo [FULL]   Полная индексация (все файлы)
if "%FORCE_INDEX%"=="1" echo [FORCE]  Принудительная переиндексация (игнорируем hash)

:: Фоновый режим для больших проектов
if "%BACKGROUND%"=="1" (
    for /f %%a in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmm"') do set "DATESTAMP=%%a"
    set "LOG_FILE=%FRAMEWORK_ROOT%\logs\index-!DATESTAMP!.log"
    echo [BACKGROUND] Запуск в фоновом режиме...
    echo [LOG] Лог будет записан в: !LOG_FILE!
    echo.
    set "MODE_FLAG="
    if "!MODE!"=="docs" set "MODE_FLAG=--docs-only"
    if "!MODE!"=="bsl" set "MODE_FLAG=--bsl-only"
    set "EXTRA_FLAGS="
    if "!FULL_INDEX!"=="1" set "EXTRA_FLAGS=!EXTRA_FLAGS! --full"
    if "!FORCE_INDEX!"=="1" set "EXTRA_FLAGS=!EXTRA_FLAGS! --force"
    start "" /b cmd /c ""%~f0" "%INPUT%" !MODE_FLAG! !EXTRA_FLAGS! > "!LOG_FILE!" 2>&1"
    echo [OK] Индексация запущена в фоне. Проверьте лог позже.
    goto :END
)
echo.

:: ============================================================
:: 1. Индексация для 1c-docs-rag (документация + код)
:: ============================================================
if "%MODE%"=="bsl" goto :BSL_INDEX

echo ────────────────────────────────────────────────────────────
echo [1/2] 1c-docs-rag индексация (семантический поиск документации)
echo ────────────────────────────────────────────────────────────
echo.

:: Остановка MCP сервера 1c-docs-rag (освобождаем БД)
echo [MCP] Остановка 1c-docs-rag MCP сервера...
powershell -NoProfile -Command "Get-Process python -EA SilentlyContinue | Where-Object {$_.CommandLine -like '*mcp_server.py*'} | Stop-Process -Force -EA SilentlyContinue" >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] MCP сервер остановлен

if exist "%SMART_SCRIPT%" (
    set "FULL_FLAG="
    set "FORCE_FLAG="
    if "%FULL_INDEX%"=="1" set "FULL_FLAG=--full"
    if "%FORCE_INDEX%"=="1" set "FORCE_FLAG=--force"
    python "%SMART_SCRIPT%" --path "%FOLDER_PATH%" --languages "%LANGUAGES%" !FULL_FLAG! !FORCE_FLAG!
    if !ERRORLEVEL! EQU 0 (
        echo [OK] 1c-docs-rag индексация завершена
    ) else (
        echo [ERROR] 1c-docs-rag индексация завершена с ошибкой ^(код: !ERRORLEVEL!^)
        set "EXIT_CODE=1"
    )
) else (
    echo [ERROR] Скрипт не найден: %SMART_SCRIPT%
    set "EXIT_CODE=1"
)

echo [INFO] MCP сервер 1c-docs-rag перезапустится автоматически при следующем вызове
echo.

if "%MODE%"=="docs" goto :DONE

:BSL_INDEX
:: ============================================================
:: 2. Индексация для bsl-semantic-search (BSL эмбеддинги + Ollama)
:: ============================================================
echo ────────────────────────────────────────────────────────────
echo [2/2] bsl-semantic-search индексация (BSL эмбеддинги)
echo ────────────────────────────────────────────────────────────
echo.

set BSL_SEARCH_ROOT=D:\1C-Enterprise_Framework\bsl-semantic-search
set BSL_SCRIPT=%BSL_SEARCH_ROOT%\scripts\indexing\bsl_indexer_async.py
set BSL_OUTPUT=%BSL_SEARCH_ROOT%\data\index

if not exist "%BSL_SCRIPT%" (
    echo [SKIP] BSL indexer не найден: %BSL_SCRIPT%
    echo        bsl-semantic-search не установлен
    echo.
    goto :DONE
)

:: Проверка и запуск Ollama (требуется для BSL эмбеддингов)
set "OLLAMA_EXE="
where ollama >nul 2>&1 && set "OLLAMA_EXE=ollama"
if "!OLLAMA_EXE!"=="" if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if "!OLLAMA_EXE!"=="" if exist "C:\Program Files\Ollama\ollama.exe" set "OLLAMA_EXE=C:\Program Files\Ollama\ollama.exe"

if "!OLLAMA_EXE!"=="" (
    echo [ERROR] Ollama не установлен. BSL индексация невозможна.
    echo         Установите: https://ollama.com/download
    set "EXIT_CODE=1"
    echo.
    goto :DONE
)

echo [CHECK] Проверка Ollama...
curl -s --connect-timeout 3 http://localhost:11434/api/tags >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [START] Запуск Ollama...
    start "" "!OLLAMA_EXE!" serve
    echo [WAIT] Ожидание готовности Ollama...
    set "OLLAMA_READY=0"
    for /L %%W in (1,1,15) do (
        if "!OLLAMA_READY!"=="0" (
            ping -n 2 127.0.0.1 >nul 2>&1
            curl -s --connect-timeout 2 http://localhost:11434/api/tags >nul 2>&1
            if !ERRORLEVEL! EQU 0 set "OLLAMA_READY=1"
        )
    )
    if "!OLLAMA_READY!"=="0" (
        echo [ERROR] Ollama не запустился за 30 секунд. BSL индексация пропущена.
        set "EXIT_CODE=1"
        echo.
        goto :DONE
    )
)
echo [OK] Ollama доступен

:: Запуск BSL indexer из его рабочей директории (для корректных импортов)
pushd "%BSL_SEARCH_ROOT%"
python "%BSL_SCRIPT%" "%FOLDER_PATH%" --output "%BSL_OUTPUT%"
if !ERRORLEVEL! EQU 0 (
    echo [OK] bsl-semantic-search индексация завершена
) else (
    echo [ERROR] bsl-semantic-search индексация завершена с ошибкой ^(код: !ERRORLEVEL!^)
    set "EXIT_CODE=1"
)
popd
echo.

:DONE
echo ════════════════════════════════════════════════════════════
if "!EXIT_CODE!"=="0" (
    echo [DONE] Индексация завершена успешно!
) else (
    echo [DONE] Индексация завершена с ошибками!
)
echo.
echo Теперь доступен семантический поиск:
echo   - mcp__bsl-semantic-search__bsl_search("запрос")
echo   - mcp__bsl-semantic-search__bsl_stats()
echo ════════════════════════════════════════════════════════════
goto :END

:LIST
echo.
echo Доступные проекты для индексации:
echo ──────────────────────────────────
if exist "%SMART_SCRIPT%" (
    python "%SMART_SCRIPT%" --list
) else (
    echo [ERROR] Скрипт не найден: %SMART_SCRIPT%
)
echo.
echo Использование: index-folder.bat "имя_проекта"
goto :END

:USAGE
echo.
echo Использование:
echo   index-folder.bat "путь\к\папке"                    Индексация по пути
echo   index-folder.bat "имя_проекта"                     Индексация по имени проекта
echo   index-folder.bat --list                            Список доступных проектов
echo   index-folder.bat "путь" --docs-only                Только 1c-docs-rag
echo   index-folder.bat "путь" --bsl-only                 Только bsl-semantic-search
echo   index-folder.bat "путь" --background               Запустить в фоне
echo   index-folder.bat "путь" --full                     Полная индексация (все файлы)
echo   index-folder.bat "путь" --force                    Принудительная переиндексация
echo   index-folder.bat "путь" --languages bsl,js,py      Указать языки
echo   index-folder.bat --help                            Эта справка
echo.
echo Примеры:
echo   index-folder.bat "260304_GKSTCPLK-2182"
echo   index-folder.bat "260304_GKSTCPLK-2182" --full --force
echo   index-folder.bat "D:\Projects\MyProject\src"
echo.
goto :END

:END
endlocal & exit /b %EXIT_CODE%
