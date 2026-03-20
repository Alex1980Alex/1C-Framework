# Template: Python Code Quality

name: python-quality
scope: "src/**/*.py"
metric: ruff + mypy errors count
direction: lower is better
verify: |
  ruff check src/ --output-format json 2>/dev/null | python -c "import sys,json; print(len(json.load(sys.stdin)))"
test: pytest tests/ -q --tb=short

## Executor

- Запусти `ruff check src/ --statistics` — найди самую частую категорию ошибок
- Исправь ВСЕ файлы с этой категорией за одну итерацию
- Используй `ruff check --fix --select {code}` для автоисправимых ошибок
- Для mypy: фокус на одном типе ошибки (missing-return, incompatible-type)
- Один коммит = одна категория

## Reviewer

- `ruff check src/` — ошибок стало меньше?
- `mypy src/` — типизация не ухудшилась?
- `pytest tests/ -q` — тесты проходят?
- Нет ли новых ошибок в других категориях?
