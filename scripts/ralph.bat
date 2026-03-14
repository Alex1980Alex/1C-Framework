@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

:: ralph.bat — Ralph Wiggum autonomous loop for PDF Vector & Graph Framework (Windows)
::
:: Usage:
::   scripts\ralph.bat <max-iterations> "<prompt>"
::   scripts\ralph.bat 10 "Добавь тесты для всех модулей в src/pdf_framework/search/"
::   scripts\ralph.bat --template reindex
::   scripts\ralph.bat --template test-coverage

set "PROJECT_DIR=%~dp0.."
set "MAX_ITERATIONS=10"
set "COMPLETION_MARKER=RALPH_DONE"
set "PROMPT="
set "USE_TEMPLATE="

:: Parse arguments
:parse_args
if "%~1"=="" goto :after_args
if "%~1"=="--template" (
    set "USE_TEMPLATE=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--max-iterations" (
    set "MAX_ITERATIONS=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--help" goto :show_help
if "%~1"=="-h" goto :show_help

:: First numeric arg = max iterations, else = prompt
set "TEST_NUM=%~1"
set /a "TEST_NUM_CHECK=TEST_NUM" 2>nul
if "!TEST_NUM_CHECK!"=="%~1" (
    if "%PROMPT%"=="" (
        set "MAX_ITERATIONS=%~1"
    ) else (
        set "PROMPT=%~1"
    )
) else (
    set "PROMPT=%~1"
)
shift
goto :parse_args

:after_args

:: Apply template
if not "%USE_TEMPLATE%"=="" (
    if "%USE_TEMPLATE%"=="reindex" (
        echo [TEMPLATE] reindex
        set "PROMPT=ЗАДАЧА: Проверить и исправить полный пайплайн индексации PDF-документа. КОНТЕКСТ: PDF Vector ^& Graph Framework, Hybrid Loader, Qdrant + BM25 FTS5 + Graph, FastAPI localhost:8000. КРИТЕРИИ ЗАВЕРШЕНИЯ: 1. API /documents/upload принимает PDF и возвращает 200. 2. Все чанки имеют page_number и section_title. 3. BM25 индекс синхронизирован с Qdrant. 4. Поиск /search/ask возвращает релевантный ответ. 5. Нет ошибок в логах. Когда ВСЕ критерии выполнены: RALPH_DONE"
    ) else if "%USE_TEMPLATE%"=="test-coverage" (
        echo [TEMPLATE] test-coverage
        set "PROMPT=ЗАДАЧА: Увеличить покрытие unit-тестами до ^>= 80%% для основных модулей. КОНТЕКСТ: pytest + pytest-asyncio. Модули: src/pdf_framework/search/, processing/, chains/. КРИТЕРИИ ЗАВЕРШЕНИЯ: 1. Все тесты проходят. 2. Покрытие ^>= 80%% для ключевых модулей. 3. Тесты проверяют реальное поведение. Когда ВСЕ критерии выполнены: RALPH_DONE"
    ) else if "%USE_TEMPLATE%"=="evaluation" (
        echo [TEMPLATE] evaluation
        set "PROMPT=ЗАДАЧА: Запустить полный цикл RAGAS-оценки и исправить деградации. КОНТЕКСТ: src/pdf_framework/evaluation/, API localhost:8000. КРИТЕРИИ ЗАВЕРШЕНИЯ: 1. Бенчмарк из 10+ вопросов прогнан. 2. faithfulness ^>= 0.8. 3. answer_relevancy ^>= 0.7. 4. Результаты сохранены в data/evaluation/. Когда ВСЕ критерии выполнены: RALPH_DONE"
    ) else if "%USE_TEMPLATE%"=="documentation" (
        echo [TEMPLATE] documentation
        set "PROMPT=ЗАДАЧА: Добавить docstrings ко всем публичным функциям и классам в src/pdf_framework/. КОНТЕКСТ: Python 3.11+, Google-style docstrings. КРИТЕРИИ ЗАВЕРШЕНИЯ: 1. Каждый публичный класс/метод/функция имеет docstring. 2. Содержат описание, Args, Returns. 3. Нет заглушек. 4. Код запускается без ошибок. Когда ВСЕ критерии выполнены: RALPH_DONE"
    ) else if "%USE_TEMPLATE%"=="lint" (
        echo [TEMPLATE] lint
        set "PROMPT=ЗАДАЧА: Исправить все предупреждения и ошибки линтера. КОНТЕКСТ: ruff или flake8, black. КРИТЕРИИ ЗАВЕРШЕНИЯ: 1. ruff check src/ = 0 ошибок. 2. Импорты отсортированы. 3. Код отформатирован. 4. Нет unused imports. Когда ВСЕ критерии выполнены: RALPH_DONE"
    ) else if "%USE_TEMPLATE%"=="quality" (
        echo [TEMPLATE] quality
        set "PROMPT=ЗАДАЧА: Автономный цикл улучшения качества Python-кода (AutoResearch-подход). КОНТЕКСТ: Проект D:\1С-Framework. Python 3.11+. Инструменты: ruff, mypy. ПРОТОКОЛ КАЖДОЙ ИТЕРАЦИИ: 1. ЗАМЕР: запусти ruff check src/ --output-format json и подсчитай ошибки. Запусти mypy src/ и подсчитай ошибки. Запиши числа. 2. КОММИТ: git commit текущее состояние (чтобы можно было откатить). 3. ИЗМЕНЕНИЕ: выбери ОДНУ категорию ошибок (самую частую по ruff или mypy) и исправь ВО ВСЕХ файлах. 4. ПРОВЕРКА: запусти ruff check и mypy снова. Сравни с замером из п.1. 5. РЕШЕНИЕ: если ошибок стало меньше — оставь (keep). Если больше или код сломался — git revert HEAD --no-edit (discard). 6. ЛОГ: добавь строку в data/autoresearch-results.tsv в формате: iteration TAB commit TAB ruff_errors TAB mypy_errors TAB delta TAB status TAB description. 7. ПОВТОР: перейди к следующей итерации. КРИТЕРИИ ЗАВЕРШЕНИЯ: 1. ruff check src/ = 0 ошибок. 2. mypy src/ = 0 ошибок типизации. 3. Ни одно исправление не сломало существующий код. 4. Файл data/autoresearch-results.tsv содержит полный лог. Когда ВСЕ критерии выполнены: RALPH_DONE"
    ) else (
        echo [ERROR] Unknown template: %USE_TEMPLATE%
        echo Available: reindex, test-coverage, evaluation, documentation, lint, quality
        exit /b 1
    )
)

if "%PROMPT%"=="" goto :show_help

:: Create log directory
if not exist "%PROJECT_DIR%\data" mkdir "%PROJECT_DIR%\data"
set "LOG_FILE=%PROJECT_DIR%\data\ralph_log_%date:~0,4%%date:~5,2%%date:~8,2%.txt"
set "ACTIVE_FILE=%PROJECT_DIR%\.claude\hooks\.ralph_active"

echo === Ralph Wiggum Autonomous Loop ===
echo Max iterations: %MAX_ITERATIONS%
echo Completion marker: %COMPLETION_MARKER%
echo Log: %LOG_FILE%
echo.

cd /d "%PROJECT_DIR%"

:: Activate Ralph mode — Stop Hook will check this file
echo 1 > "%ACTIVE_FILE%"

set "ITERATION=0"

:loop
if %ITERATION% GEQ %MAX_ITERATIONS% goto :max_reached
set /a "ITERATION+=1"

echo === Iteration %ITERATION% / %MAX_ITERATIONS% [%date% %time%] ===
echo === Iteration %ITERATION% / %MAX_ITERATIONS% [%date% %time%] === >> "%LOG_FILE%"

:: Run Claude Code
claude -p "%PROMPT% Текущая итерация: %ITERATION% из %MAX_ITERATIONS%. Проверь git log --oneline -5 и git diff --stat для контекста. Если задача полностью завершена по ВСЕМ критериям, включи в конец ответа строку: %COMPLETION_MARKER%. Если нет — продолжай работу." --dangerously-skip-permissions > "%TEMP%\ralph_output.txt" 2>&1
type "%TEMP%\ralph_output.txt"
type "%TEMP%\ralph_output.txt" >> "%LOG_FILE%"

:: Check completion marker
findstr /C:"%COMPLETION_MARKER%" "%TEMP%\ralph_output.txt" >nul 2>&1
if %errorlevel%==0 (
    echo === Task completed at iteration %ITERATION% ===
    echo === Task completed at iteration %ITERATION% === >> "%LOG_FILE%"
    del "%ACTIVE_FILE%" 2>nul
    exit /b 0
)

echo === Iteration %ITERATION% done, continuing... ===
echo === Iteration %ITERATION% done, continuing... === >> "%LOG_FILE%"
timeout /t 2 /nobreak >nul
goto :loop

:max_reached
echo === Max iterations reached (%MAX_ITERATIONS%) ===
echo === Max iterations reached (%MAX_ITERATIONS%) === >> "%LOG_FILE%"
del "%ACTIVE_FILE%" 2>nul
exit /b 1

:show_help
echo Ralph Wiggum — Autonomous Loop for PDF Framework (Windows)
echo.
echo Usage:
echo   scripts\ralph.bat ^<max-iterations^> "^<prompt^>"
echo   scripts\ralph.bat --template ^<name^> [--max-iterations N]
echo.
echo Templates:
echo   reindex         Full reindex pipeline verification
echo   test-coverage   Increase test coverage to 80%%+
echo   evaluation      Run RAGAS evaluation suite
echo   documentation   Add docstrings to public API
echo   lint            Fix all linter warnings
echo.
echo Options:
echo   --max-iterations N   Set max iterations (default: 10)
echo   --help               Show this help
exit /b 0
