#!/bin/bash
#
# Pipeline CLI - Shell Script Example
#
# Использование:
#   ./run_pipeline.sh <project> "<task>"
#
# Примеры:
#   ./run_pipeline.sh GKSTCPLK-1872 "Добавить валидацию"
#   ./run_pipeline.sh GKSTCPLK-1996 "Исправить ошибку"
#
# Версия: 1.0.0
# Дата: 2025-12-23
#

set -e

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Проверка аргументов
if [ -z "$1" ]; then
    echo -e "${RED}Usage: $0 <project> \"<task>\"${NC}"
    echo ""
    echo "Examples:"
    echo "  $0 GKSTCPLK-1872 \"Добавить валидацию\""
    exit 1
fi

if [ -z "$2" ]; then
    echo -e "${RED}Error: Task description is required${NC}"
    echo "Usage: $0 <project> \"<task>\""
    exit 1
fi

PROJECT="$1"
TASK="$2"

echo "============================================================"
echo -e "${BLUE}Pipeline CLI Runner${NC}"
echo "============================================================"
echo ""
echo -e "Project: ${GREEN}$PROJECT${NC}"
echo -e "Task: ${YELLOW}$TASK${NC}"
echo ""

# Переходим в корень проекта
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

# Проверяем наличие Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR] Python3 not found${NC}"
    exit 1
fi

# Функция для запуска CLI
run_cli() {
    python3 -m shared.pipeline.cli "$@"
}

# Показываем статус перед запуском
echo -e "${BLUE}[1/4] Checking current status...${NC}"
run_cli status || true
echo ""

# Показываем конфигурацию
echo -e "${BLUE}[2/4] Checking configuration...${NC}"
run_cli config show || true
echo ""

# Запускаем pipeline
echo -e "${BLUE}[3/4] Starting pipeline...${NC}"
echo ""
if run_cli run --project "$PROJECT" --task "$TASK"; then
    RUN_RESULT=0
else
    RUN_RESULT=$?
fi
echo ""

# Показываем результат
echo -e "${BLUE}[4/4] Checking result...${NC}"
run_cli status || true
echo ""

echo "============================================================"
if [ $RUN_RESULT -eq 0 ]; then
    echo -e "${GREEN}[SUCCESS] Pipeline completed successfully${NC}"
else
    echo -e "${RED}[FAILED] Pipeline failed with exit code: $RUN_RESULT${NC}"
fi
echo "============================================================"

exit $RUN_RESULT
