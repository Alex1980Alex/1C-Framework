---
name: tenacity-retry
description: "Retry с tenacity: декораторы, backoff, jitter, async. Триггеры: 'retry', 'tenacity', 'backoff', 'exponential backoff', 'jitter', 'retry decorator', 'повторные попытки', 'rate limit retry'. НЕ для LangGraph RetryPolicy — используй langgraph-core."
---

# Tenacity Retry — устойчивость к сбоям в PDF Framework

## Обзор

Tenacity — стандартная Python-библиотека для retry-логики (15M+ скачиваний/неделю). Декораторный подход, работает с sync и async, поддерживает exponential backoff, jitter, условные retries. В PDF Framework есть готовые декораторы в `src/pdf_framework/utils/retry.py`.

---

## Быстрый справочник

| Задача | Действие |
|--------|----------|
| Retry LLM вызова | `@retry_llm_call` (5 попыток, exp jitter, 120s max) |
| Retry embedding | `@retry_embedding` (5 попыток, 90s max, +RuntimeError) |
| Retry БД операции | `@retry_db_operation` (3 попытки, 0.5s fixed) |
| Retry HTTP запроса | `@retry_network` (4 попытки, exp jitter, 60s max) |
| Кастомный retry | `create_retry(max_attempts=N, ...)` |
| Установка | `pip install tenacity` (>=9.1.4, Python >=3.10) |

---

## Готовые декораторы фреймворка

```python
from src.pdf_framework.utils.retry import (
    retry_llm_call,
    retry_embedding,
    retry_db_operation,
    retry_network,
    create_retry,
)
```

### retry_llm_call — для API вызовов к LLM

```python
@retry_llm_call
async def call_claude(prompt: str) -> str:
    return await client.messages.create(
        model="claude-sonnet-4-5-20250929",
        messages=[{"role": "user", "content": prompt}],
    )
```

| Параметр | Значение |
|----------|----------|
| Попытки | 5 или 120s (что раньше) |
| Ожидание | Exponential jitter: 1s, 2s, 4s ... max 60s, +/-2s |
| Retries на | `TimeoutError`, `ConnectionError`, `OSError` |
| reraise | True (оригинальное исключение) |

### retry_embedding — для embedding API

```python
@retry_embedding
async def embed_text(text: str) -> list[float]:
    return await embedder.embed_query(text)
```

Отличие от LLM: короче таймауты (90s), ловит `RuntimeError` (CUDA/model loading).

### retry_db_operation — для Qdrant/SQLite

```python
@retry_db_operation
async def upsert_points(collection: str, points: list) -> None:
    await qdrant.upsert(collection_name=collection, points=points)
```

3 попытки, fixed 0.5s — БД-операции быстрые, длинный backoff не нужен.

### retry_network — для HTTP

```python
@retry_network
async def fetch_url(url: str) -> bytes:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content
```

### create_retry — фабрика кастомных конфигов

```python
retry_heavy = create_retry(
    max_attempts=10,
    max_delay=300.0,
    initial_wait=2.0,
    max_wait=120.0,
    jitter=5.0,
    retry_on=(TimeoutError, ConnectionError),
)

@retry_heavy
async def heavy_operation() -> None: ...
```

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `max_attempts` | 3 | Макс попыток |
| `max_delay` | None | Общий таймаут (секунды) |
| `initial_wait` | 1.0 | Начальная задержка (секунды) |
| `max_wait` | 60.0 | Макс задержка (секунды) |
| `jitter` | 1.0 | Случайный разброс (секунды) |
| `retry_on` | Timeout+Connection+OS | Типы исключений для retry |

---

## Tenacity API — основные компоненты

### Wait-стратегии

```python
from tenacity import (
    wait_fixed,              # Постоянная задержка
    wait_random,             # Случайная в диапазоне
    wait_exponential,        # Экспоненциальный backoff
    wait_random_exponential, # Full Jitter (AWS стиль)
    wait_exponential_jitter, # Google Cloud стиль
    wait_chain,              # Последовательная цепочка
    wait_combine,            # Суммирование стратегий
)

# Комбинирование через +
wait = wait_fixed(3) + wait_random(0, 2)   # 3-5 секунд

# Параметры wait_exponential_jitter (рекомендуется)
wait = wait_exponential_jitter(
    initial=1,    # Начальная задержка
    max=60,       # Потолок
    exp_base=2,   # База экспоненты
    jitter=2,     # +/- случайный разброс
)
```

### Stop-стратегии

```python
from tenacity import stop_after_attempt, stop_after_delay

# Комбинирование через |
stop = stop_after_attempt(5) | stop_after_delay(120)  # Что наступит раньше
```

### Retry-условия

```python
from tenacity import (
    retry_if_exception_type,      # Retry на конкретные exceptions
    retry_if_not_exception_type,  # Retry на ВСЕ кроме указанных
    retry_if_result,              # Retry если результат = predicate
    retry_if_exception_message,   # Retry если message содержит строку
    retry_any, retry_all,         # Комбинаторы
)

# Комбинирование через | и &
retry = (
    retry_if_exception_type(TimeoutError) |
    retry_if_result(lambda x: x is None)
)
```

### Callbacks

```python
from tenacity import before_log, after_log, before_sleep_log

@retry(
    before=before_log(logger, logging.DEBUG),
    after=after_log(logger, logging.DEBUG),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def fn(): ...

# Кастомный callback
def my_callback(retry_state):
    print(f"Attempt #{retry_state.attempt_number}")
    print(f"Exception: {retry_state.outcome.exception()}")
    print(f"Elapsed: {retry_state.seconds_since_start}s")
```

### Runtime override

```python
@retry(stop=stop_after_attempt(3))
def fn(): ...

# Переопределить параметры для одного вызова
fn.retry_with(stop=stop_after_attempt(10))()

# Статистика
fn.retry.statistics  # {"attempt_number": 3, ...}
```

### Async — бесшовная поддержка

```python
# @retry автоматически определяет async
@retry(stop=stop_after_attempt(3))
async def async_fn():
    await some_operation()

# Или через AsyncRetrying context manager
from tenacity import AsyncRetrying

async for attempt in AsyncRetrying(stop=stop_after_attempt(3)):
    with attempt:
        result = await some_operation()
```

---

## Шаблоны

### Шаблон 1: Retry с rate limit (LLM API)

```python
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type

@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    reraise=True,
)
async def call_api(prompt: str) -> str:
    return await [CLIENT].messages.create(
        model="[MODEL]",
        messages=[{"role": "user", "content": prompt}],
    )
```

### Шаблон 2: Retry с fallback значением

```python
from tenacity import retry, stop_after_attempt, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(ConnectionError),
    retry_error_callback=lambda state: "[DEFAULT_VALUE]",
)
def fetch_with_fallback() -> str:
    return requests.get("[URL]").text
```

### Шаблон 3: Code block retry (без декоратора)

```python
from tenacity import Retrying, stop_after_attempt

for attempt in Retrying(stop=stop_after_attempt(3)):
    with attempt:
        result = dangerous_operation()
# result доступен после цикла
```

---

## Диагностика

| Проблема | Причина | Решение |
|----------|---------|---------|
| Бесконечный retry | Нет stop condition | Добавить `stop=stop_after_attempt(N)` |
| RetryError вместо оригинального | `reraise=False` (default) | Установить `reraise=True` |
| Retry на ValueError/TypeError | Слишком широкий retry condition | Использовать `retry_if_exception_type(...)` |
| Thundering herd при восстановлении | Фиксированный wait без jitter | Использовать `wait_exponential_jitter` |
| Retry не работает с async | Старая версия tenacity | Обновить до >=9.0 |
| Логи не показывают retries | Нет callback | Добавить `before_sleep=before_sleep_log(...)` |

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `@retry` без параметров | Бесконечный retry без задержки | `@retry(stop=stop_after_attempt(5), wait=...)` |
| `retry_if_exception_type(Exception)` | Retry на программные ошибки | Только transient: TimeoutError, ConnectionError |
| `wait_fixed(1)` для API | Thundering herd | `wait_exponential_jitter(initial=1, max=60)` |
| `from tenacity import *` | Wildcard import | Явные импорты |
| Свой retry-цикл вместо tenacity | Boilerplate, нет jitter | Использовать декораторы из utils/retry.py |

---

## Ссылки

| Ресурс | URL |
|--------|-----|
| Документация | https://tenacity.readthedocs.io/ |
| GitHub | https://github.com/jd/tenacity |
| PyPI | https://pypi.org/project/tenacity/ |
| API Reference | https://tenacity.readthedocs.io/en/latest/api.html |
| AWS Exponential Backoff | https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/ |
