# Contributing

## Разработка

### Установка

```bash
uv venv .venv
.venv\Scripts\activate
uv pip install -e ".[dev,qdrant,docling,morphology]"
```

### Запуск тестов

```bash
pytest tests/ --cov=src
```

### Линтинг

```bash
ruff check src/
ruff format src/
mypy src/
```

### Структура

- Все store implementations наследуют abstract base classes из `*/base.py`
- Data contracts через Pydantic models в `schemas/`
- Async-first: все I/O операции через `async`
- Config через `pydantic-settings` с `__` delimiter

### Pull Request

1. Создайте ветку от `main`
2. Убедитесь что `ruff check` и `pytest` проходят
3. Добавьте запись в `CHANGELOG.md`
4. Опишите изменения в PR description

### Стиль кода

- Python 3.11+
- Line length: 100 (`ruff`)
- Lint rules: E, F, I, N, W, UP
- Docstrings: Google style (для публичных API)
