# Template: Test Coverage

name: test-coverage
scope: "tests/**/*.py"
metric: coverage %
direction: higher is better
verify: |
  pytest --cov=src --cov-report=json -q 2>/dev/null && python -c "import json; d=json.load(open('coverage.json')); print(f\"METRIC: {d['totals']['percent_covered']:.1f}\")"
test: pytest tests/ -q --tb=short

## Executor

- `pytest --cov=src --cov-report=term-missing` — найди модуль с наименьшим покрытием
- Напиши тесты для ОДНОГО непокрытого модуля
- Используй pytest-asyncio для async функций
- Реальные тесты, а не моки (мок скрывает баги)
- Тестируй edge cases, не только happy path

## Reviewer

- `pytest tests/ -q` — все тесты проходят?
- Coverage вырос?
- Тесты проверяют реальное поведение (не просто `assert True`)?
- Нет чрезмерного мокирования?
