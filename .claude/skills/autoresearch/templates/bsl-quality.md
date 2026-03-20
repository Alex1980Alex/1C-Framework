# Template: BSL Code Quality

name: bsl-quality
scope: "src/bsl/**/*.bsl, src/projects/**/*.bsl"
metric: bsl_analyze errors count
direction: lower is better
verify: |
  # Через MCP: mcp__bsl-debugger__bsl_analyze
  echo "METRIC: $(bsl_analyze --format json 2>/dev/null | python -c 'import sys,json; print(len(json.load(sys.stdin)))')"
test: echo "BSL tests via bsl_execute"

## Executor

- Используй `bsl_analyze` для поиска ошибок
- Используй `bsl-platform-context` для проверки API 1С
- Исправляй ОДНУ категорию ошибок за итерацию
- Проверяй синтаксис через EDT-MCP `validate_query` для запросов

## Reviewer

- `bsl_analyze` — ошибок стало меньше?
- Нет ли новых ошибок в других категориях?
- API вызовы соответствуют платформе 8.3.27?
- Изменения в scope (не затрагивают другие модули)?
