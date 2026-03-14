#!/bin/bash
# ralph.sh — Ralph Wiggum autonomous loop for PDF Vector & Graph Framework
#
# Usage:
#   ./scripts/ralph.sh <max-iterations> "<prompt>"
#   ./scripts/ralph.sh 10 "Добавь тесты для всех модулей в src/pdf_framework/search/"
#   ./scripts/ralph.sh --template reindex
#   ./scripts/ralph.sh --template test-coverage
#
# Templates (--template):
#   reindex         — Full reindex pipeline verification
#   test-coverage   — Increase test coverage to 80%+
#   evaluation      — Run RAGAS evaluation suite
#   documentation   — Add docstrings to public API
#   lint            — Fix all linter warnings
#   quality         — AutoResearch: autonomous code quality loop (ruff+mypy)
#   1c-study        — AutoResearch: autonomous 1C configuration study (6-phase cycle)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default config
MAX_ITERATIONS=10
COMPLETION_MARKER="RALPH_DONE"
LOG_FILE="$PROJECT_DIR/data/ralph_log_$(date +%Y%m%d_%H%M%S).txt"

# Built-in templates
declare -A TEMPLATES

TEMPLATES[reindex]='ЗАДАЧА: Проверить и исправить полный пайплайн индексации PDF-документа.

КОНТЕКСТ:
- Проект: PDF Vector & Graph Framework (d:/1С-Framework)
- Индексация: Hybrid Loader → Pipeline → Qdrant + BM25 FTS5 + Graph
- API: FastAPI на localhost:8000
- Тестовый PDF: data/pdfs/ (Глава 5, 218 страниц)

КРИТЕРИИ ЗАВЕРШЕНИЯ:
1. API /documents/upload принимает PDF и возвращает 200
2. Все чанки имеют page_number и section_title в метаданных
3. BM25 индекс содержит столько же записей, сколько чанков в Qdrant
4. Поиск по API /search/ask возвращает релевантный ответ с источниками
5. Нет ошибок в логах сервера

Когда ВСЕ критерии выполнены: RALPH_DONE'

TEMPLATES[test-coverage]='ЗАДАЧА: Увеличить покрытие unit-тестами до >= 80% для основных модулей фреймворка.

КОНТЕКСТ:
- Проект: PDF Vector & Graph Framework (d:/1С-Framework)
- Тесты: pytest + pytest-asyncio
- Основные модули: src/pdf_framework/search/, src/pdf_framework/processing/, src/pdf_framework/chains/
- Команда: pytest tests/ -v --tb=short

КРИТЕРИИ ЗАВЕРШЕНИЯ:
1. Все тесты в tests/ проходят (pytest exit code 0)
2. Покрытие >= 80% для search/manager.py, search/bm25_store.py, chains/qa/retrieval_qa.py
3. Каждый тест проверяет реальное поведение (не заглушки)
4. Тесты используют pytest fixtures и asyncio

ПОРЯДОК РАБОТЫ:
1. Запусти pytest --tb=short чтобы увидеть текущее состояние
2. Найди модули с наименьшим покрытием
3. Напиши тесты, запусти, исправь если падают
4. Коммить после каждого модуля: "[RALPH] Tests: module_name"

Когда ВСЕ критерии выполнены: RALPH_DONE'

TEMPLATES[evaluation]='ЗАДАЧА: Запустить полный цикл RAGAS-оценки и исправить деградации качества.

КОНТЕКСТ:
- Проект: PDF Vector & Graph Framework (d:/1С-Framework)
- Оценка: src/pdf_framework/evaluation/
- API: localhost:8000
- Метрики: faithfulness, answer_relevancy, context_precision

КРИТЕРИИ ЗАВЕРШЕНИЯ:
1. Бенчмарк из 10+ вопросов прогнан через /search/ask
2. Средний faithfulness >= 0.8
3. Средний answer_relevancy >= 0.7
4. Нет регрессий по сравнению с предыдущим запуском (если есть история)
5. Результаты сохранены в data/evaluation/

Когда ВСЕ критерии выполнены: RALPH_DONE'

TEMPLATES[documentation]='ЗАДАЧА: Добавить docstrings ко всем публичным функциям и классам в src/pdf_framework/.

КОНТЕКСТ:
- Проект: PDF Vector & Graph Framework (d:/1С-Framework)
- Язык: Python 3.11+
- Формат: Google-style docstrings
- Язык документации: русский для описаний, английский для параметров

КРИТЕРИИ ЗАВЕРШЕНИЯ:
1. Каждый публичный класс, метод, функция в src/pdf_framework/ имеет docstring
2. Docstrings содержат: описание, Args, Returns, Raises (где применимо)
3. Нет пустых docstrings-заглушек
4. Код запускается без ошибок (python -c "import src.pdf_framework")

ПОРЯДОК РАБОТЫ:
1. Найди файлы без docstrings (grep -rL "\"\"\"" src/pdf_framework/*.py)
2. Добавь docstrings, начиная с публичных API (search/, chains/, agents/)
3. Коммить после каждого модуля

Когда ВСЕ критерии выполнены: RALPH_DONE'

TEMPLATES[lint]='ЗАДАЧА: Исправить все предупреждения и ошибки линтера в проекте.

КОНТЕКСТ:
- Проект: PDF Vector & Graph Framework (d:/1С-Framework)
- Линтер: ruff (если установлен) или flake8
- Форматтер: black или ruff format

КРИТЕРИИ ЗАВЕРШЕНИЯ:
1. ruff check src/ --fix возвращает 0 ошибок
2. Импорты отсортированы (isort)
3. Код отформатирован (black/ruff format)
4. Нет unused imports

Когда ВСЕ критерии выполнены: RALPH_DONE'

TEMPLATES[quality]='ЗАДАЧА: Автономный цикл улучшения качества Python-кода (AutoResearch-подход).

КОНТЕКСТ:
- Проект: PDF Vector & Graph Framework (d:/1С-Framework)
- Python 3.11+
- Инструменты: ruff (lint), mypy (типизация)
- Лог результатов: data/autoresearch-results.tsv

ПРОТОКОЛ КАЖДОЙ ИТЕРАЦИИ:
1. ЗАМЕР: запусти `ruff check src/ --output-format json` и подсчитай ошибки.
   Запусти `mypy src/` и подсчитай строки с ": error:". Запиши оба числа.
2. КОММИТ: `git add -A && git commit -m "[RALPH] quality: pre-check iteration N"`
   (чтобы можно было откатить если станет хуже).
3. ИЗМЕНЕНИЕ: выбери ОДНУ самую частую категорию ошибок (по ruff или mypy)
   и исправь её ВО ВСЕХ файлах. Делай минимальные изменения — не рефактори код.
4. ПРОВЕРКА: запусти ruff check и mypy снова. Сравни с замером из п.1.
5. РЕШЕНИЕ:
   - Если ошибок стало МЕНЬШЕ → keep, `git add -A && git commit -m "[RALPH] quality: fix <category>"`
   - Если ошибок стало БОЛЬШЕ или код сломался → `git revert HEAD --no-edit` (discard)
6. ЛОГ: добавь строку в data/autoresearch-results.tsv:
   iteration<TAB>commit<TAB>ruff_errors<TAB>mypy_errors<TAB>delta<TAB>status<TAB>description
7. ПОВТОР: перейди к следующей итерации.

ВАЖНЫЕ ПРАВИЛА:
- НЕ удаляй функциональный код ради уменьшения ошибок
- НЕ добавляй # type: ignore без крайней необходимости
- НЕ трогай файлы в .claude/, docs/, data/, migrations/
- Одна итерация = одна категория ошибок = один коммит
- Если 3 раза подряд discard — попробуй радикально другой подход

КРИТЕРИИ ЗАВЕРШЕНИЯ:
1. ruff check src/ = 0 ошибок
2. mypy src/ = 0 ошибок типизации (или стабильно уменьшается к нулю)
3. Ни одно исправление не сломало существующий код
4. data/autoresearch-results.tsv содержит полный лог всех итераций

Когда ВСЕ критерии выполнены: RALPH_DONE'

# Parse arguments
show_help() {
    echo -e "${BLUE}Ralph Wiggum — Autonomous Loop for PDF Framework${NC}"
    echo ""
    echo "Usage:"
    echo "  $0 <max-iterations> \"<prompt>\""
    echo "  $0 --template <name> [--max-iterations N]"
    echo ""
    echo "Templates:"
    echo "  reindex         Full reindex pipeline verification"
    echo "  test-coverage   Increase test coverage to 80%+"
    echo "  evaluation      Run RAGAS evaluation suite"
    echo "  documentation   Add docstrings to public API"
    echo "  lint            Fix all linter warnings"
    echo "  quality         AutoResearch: autonomous code quality loop (ruff+mypy, measure-fix-revert)"
    echo ""
    echo "Options:"
    echo "  --max-iterations N   Set max iterations (default: 10)"
    echo "  --help               Show this help"
}

PROMPT=""
USE_TEMPLATE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --template)
            USE_TEMPLATE="$2"
            shift 2
            ;;
        --max-iterations)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        *)
            if [[ -z "$PROMPT" ]] && [[ "$1" =~ ^[0-9]+$ ]]; then
                MAX_ITERATIONS="$1"
            else
                PROMPT="$1"
            fi
            shift
            ;;
    esac
done

# Apply template if specified
if [[ -n "$USE_TEMPLATE" ]]; then
    if [[ -v "TEMPLATES[$USE_TEMPLATE]" ]]; then
        PROMPT="${TEMPLATES[$USE_TEMPLATE]}"
        echo -e "${GREEN}Using template: $USE_TEMPLATE${NC}"
    else
        echo -e "${RED}Unknown template: $USE_TEMPLATE${NC}"
        echo "Available: ${!TEMPLATES[*]}"
        exit 1
    fi
fi

if [[ -z "$PROMPT" ]]; then
    show_help
    exit 1
fi

# Ensure we're in project directory
cd "$PROJECT_DIR"

# Create log directory
mkdir -p "$(dirname "$LOG_FILE")"

# Activate Ralph mode — Stop Hook checks this flag file
ACTIVE_FILE="$PROJECT_DIR/.claude/hooks/.ralph_active"
echo "1" > "$ACTIVE_FILE"

# Cleanup on exit (normal, error, or interrupt)
cleanup() {
    rm -f "$ACTIVE_FILE"
}
trap cleanup EXIT INT TERM

echo -e "${BLUE}=== Ralph Wiggum Autonomous Loop ===${NC}"
echo -e "Max iterations: ${YELLOW}$MAX_ITERATIONS${NC}"
echo -e "Completion marker: ${YELLOW}$COMPLETION_MARKER${NC}"
echo -e "Log: $LOG_FILE"
echo -e "Project: $PROJECT_DIR"
echo ""

ITERATION=0
while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    ITERATION=$((ITERATION + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

    echo -e "${BLUE}=== Iteration $ITERATION / $MAX_ITERATIONS [$TIMESTAMP] ===${NC}" | tee -a "$LOG_FILE"

    # Run Claude Code
    claude -p "$PROMPT

Текущая итерация: $ITERATION из $MAX_ITERATIONS.
Проверь git log --oneline -5 и git diff --stat для контекста предыдущих изменений.
Если задача полностью завершена по ВСЕМ критериям, включи в конец ответа строку: $COMPLETION_MARKER
Если нет — продолжай работу над следующим пунктом." \
    --dangerously-skip-permissions 2>&1 | tee /tmp/ralph_output.txt | tee -a "$LOG_FILE"

    # Check for completion marker
    if grep -q "$COMPLETION_MARKER" /tmp/ralph_output.txt; then
        echo -e "${GREEN}=== Task completed at iteration $ITERATION ===${NC}" | tee -a "$LOG_FILE"
        exit 0
    fi

    echo -e "${YELLOW}=== Iteration $ITERATION done, continuing... ===${NC}" | tee -a "$LOG_FILE"
    sleep 2
done

echo -e "${RED}=== Max iterations reached ($MAX_ITERATIONS) ===${NC}" | tee -a "$LOG_FILE"
exit 1
