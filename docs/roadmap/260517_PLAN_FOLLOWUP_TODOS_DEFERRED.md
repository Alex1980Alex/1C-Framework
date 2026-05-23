# Follow-Up TODO (ОТЛОЖЕНО до отдельной сессии, 2026-05-17)

> **Источник:** Сессия subagent code-review 2026-05-17 ([docs/analysis/subagent_code_review_2026_05_17.md](../analysis/subagent_code_review_2026_05_17.md)) + замечания pre-commit mypy ratchet.
> **Статус:** ВСЁ ОТЛОЖЕНО до отдельной сессии. Production стабилен, срочных действий не требуется.

## Содержание

- [Пункт 1 — Полный фикс M1+M2: восстановление alias после recreate](#пункт-1--полный-фикс-m1m2)
- [Пункт 2 — Мелкие улучшения по итогам subagent review](#пункт-2--мелкие-улучшения)
- [Пункт 3 — Пробел в mypy baseline: ошибки типов chunker_base + embedder](#пункт-3--пробел-в-mypy-baseline)
- [Совместный план сессии](#совместный-план-сессии)
- [Критерии готовности](#критерии-готовности)

---

## Пункт 1 — Полный фикс M1+M2

**Баг:** `ensure_collection(recreate=True)` для имени alias уничтожает alias и создаёт standalone-коллекцию под именем alias. На данный момент закрыто только предупреждением в docstring.

**Воспроизведение (ручное):**
```bash
# Сейчас в индексере (если запустить):
python scripts/index_framework.py --recreate --collection framework_code_v1
# → удаляет framework_code_v1_mrl_1024 (физическую)
# → alias framework_code_v1 → framework_code_v1_mrl_1024 становится невалидным
# → создаёт новую физическую коллекцию "framework_code_v1" (4096d, без alias)
# Итог: MRL-сетап уничтожен, alias потерян, retrieval ломается до ручного восстановления
```

**Полный фикс (~15 строк + 1-2 теста):**

```python
# src/framework_search/indexer.py:ensure_collection

def ensure_collection(client, collection, dims, recreate=False):
    """Создаёт коллекцию если её нет; пересоздаёт при recreate=True.

    Alias-aware: если `collection` — это alias, recreate работает с
    underlying физической коллекцией, потом восстанавливает alias.
    """
    from qdrant_client.http.models import (
        CreateAlias, CreateAliasOperation, UpdateCollectionsAliases,
    )

    exists = client.collection_exists(collection)
    if exists and recreate:
        physical = resolve_physical_collection(client, collection)
        was_alias = physical != collection
        if was_alias:
            logger.info("indexer: '%s' alias->'%s'; пересоздаём физическую", collection, physical)
        client.delete_collection(physical)

        client.create_collection(
            collection_name=physical,
            vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE),
        )

        if was_alias:
            # Восстановить alias, который был уничтожен delete_collection
            client.update_collection_aliases(change_aliases_operations=[
                CreateAliasOperation(create_alias=CreateAlias(
                    collection_name=physical, alias_name=collection,
                )),
            ])
            logger.info("indexer: восстановлен alias '%s' -> '%s'", collection, physical)
        return

    if not exists:
        # Новая коллекция: создаём напрямую под именем (без alias)
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE),
        )
```

**Затронутые файлы (3, тот же паттерн):**
- [src/framework_search/indexer.py](../../src/framework_search/indexer.py) — `ensure_collection()` (основной)
- [scripts/reembed_collection.py](../../scripts/reembed_collection.py) — `client.upsert(collection_name=args.collection, ...)` должен использовать `physical` после recreate, ИЛИ alias должен быть восстановлен (предпочтительно)
- [scripts/reindex_pdf_documents.py](../../scripts/reindex_pdf_documents.py) — тот же паттерн что reembed_collection.py

**Тесты для добавления:**
- `tests/test_framework_search/test_indexer_mrl.py::test_ensure_collection_recreates_underlying_physical_when_alias`
- `tests/test_framework_search/test_indexer_mrl.py::test_ensure_collection_reestablishes_alias_after_recreate`
- Оба используют MagicMock с правильной настройкой alias

**Трудозатраты:** ~30 мин (код + тесты + smoke verification на реальном Qdrant alias).

**Риск:** Низкий — additive change, текущий путь WARNING docstring остаётся валидным для backwards-compat.

---

## Пункт 2 — Мелкие улучшения

См. [docs/analysis/subagent_code_review_2026_05_17.md](../analysis/subagent_code_review_2026_05_17.md) секция MINOR (9 пунктов, косметика).

**Приоритет для batch-фикса:**

1. **m1:** `resolve_physical_collection` молча проглатывает все исключения — добавить `logger.debug("get_aliases failed: %s", e)` (1 строка)
2. **m3:** RAPTOR `_embed_text` создаёт новый `FrameworkTEIEmbedder` на каждый вызов — кэшировать через ленивый атрибут `self._embedder` (~5 строк + close в `__aexit__` если класс async-context-managed)
3. **m4:** `reembed_collection.py` warning для `effective_dim` вводит в заблуждение — разделить на 2 отдельные log-строки для alias-resolution vs dim-coercion (~3 строки)
4. **m5:** `reindex_pdf_documents.py` путь без recreate пропускает alias-проверку — пробить embedder dim перед основным циклом, сравнить с `target_dim`, fail-fast при mismatch (~10 строк)
5. **m9:** `indexer.py:155` комментарий про допущение что короткие векторы уже нормализованы (1 строка)

**Пропустить (вне scope или risk-free как есть):**
- m2: `resolve_collection_dim` не ловит ошибки — пропускает корректно к caller'ам (текущее поведение предпочтительно)
- m6: `query_points.points` корректно для qdrant-client >= 1.7 (зафиксировано, без риска)
- m7: тест использует `dict` mock — работает корректно, реальный `VectorParamsMap` тоже совпадает с `isinstance(_, dict)`
- m8: `test_mrl_truncate_zero_vector_no_nan` — текущих assert'ов достаточно

**Трудозатраты:** ~30 мин (маленькие правки, новые тесты для косметики не требуются).

---

## Пункт 3 — Пробел в mypy baseline

**Проблема:** Pre-commit хук `mypy` падает при редактировании `src/framework_search/indexer.py` из-за транзитивных type errors в импортированных модулях:
- `src/framework_search/chunker_base.py:38` — `Missing type parameters for generic type "dict"` `[type-arg]`
- `src/framework_search/embedder.py:61` — `Function is missing a type annotation for one or more arguments` `[no-untyped-def]`
- `src/framework_search/embedder.py:85` — `Untyped decorator makes function "_post_embed_sub" untyped` `[misc]`

Baseline (`mypy-baseline.txt`) содержит записи `chunker_base.py:0` и `embedder.py:0` (line-stripped форма), но pre-commit хук mypy, видимо, **не использует mypy_baseline filter**. Требуется расследование.

**Задачи расследования:**

1. Проверить `.pre-commit-config.yaml` команду хука `mypy` — использует ли `mypy --baseline-file ...` или `python -m mypy_baseline filter`?
2. Если baseline НЕ подключён: настроить pre-commit чтобы фильтровать через mypy_baseline
3. Если baseline подключён но не совпадает: расследовать почему line-stripped записи не подавляют ошибки

**Альтернатива (быстрее, но менее чисто):** Зафиксить реальные type errors:

```python
# chunker_base.py:38 — добавить type parameters
metadata: dict[str, Any] = field(default_factory=dict)  # было: metadata: dict

# embedder.py:61 — аннотировать параметры
def _build_post_payload(self, texts: list[str], is_query: bool) -> dict[str, Any]:
    # ...

# embedder.py:85 — добавить тип к функции под декоратором
@retry(...)
def _post_embed_sub(self, payload: dict[str, Any]) -> list[list[float]]:
    # ...
```

**Трудозатраты:**
- Путь расследования: ~15-30 мин
- Путь прямого фикса: ~30-45 мин (3 правки файлов + тест)

**Риск:** Низкий — чистые добавления type annotations, поведение не меняется.

**Почему отложено:** Текущие коммиты проходят через auto-save (auto-save не запускает pre-commit hooks). Ручные коммиты с изменениями в indexer.py блокируются до разрешения. Прагматичная мера — использовать auto-save для изменений в indexer.py ИЛИ починить baseline plumbing.

---

## Совместный план сессии

**Рекомендованный порядок:**
1. Пункт 3 (mypy baseline) первым — разблокирует будущие коммиты indexer.py
2. Пункт 1 (M1+M2 fix) — собственно фикс бага чистыми коммитами
3. Пункт 2 (минорки) — собрать одним коммитом "subagent review minors"

**Оценочный итог:** 1.5-2 часа.

**Проверка скиллов перед стартом:**
- `Skill('qdrant-operations')` — паттерны alias API
- `Skill('framework-search')` — контекст indexer.py
- `Skill('code-verify')` — верифицировать M1+M2 fix через test + smoke

---

## Критерии готовности

- [ ] Пункт 1: `ensure_collection(recreate=True)` для alias корректно пересоздаёт underlying физическую И восстанавливает alias. Smoke verified на реальном Qdrant.
- [ ] Пункт 1: 2 новых теста в `test_indexer_mrl.py` PASS (mock-based, реальный Qdrant для CI не требуется)
- [ ] Пункт 1: WARNING docstring удалён из `ensure_collection` (баг теперь зафикшен)
- [ ] Пункт 2: 5 минорных улучшений применены (m1, m3, m4, m5, m9), commit message ссылается на какие именно
- [ ] Пункт 3: Pre-commit хук `mypy` работает с mypy_baseline filter ИЛИ транзитивные ошибки зафикшены у источника
- [ ] Все изменения запушены в origin

---

## Связанные документы

- [docs/analysis/subagent_code_review_2026_05_17.md](../analysis/subagent_code_review_2026_05_17.md) — полный отчёт subagent review
- [src/framework_search/indexer.py](../../src/framework_search/indexer.py) — основной файл с M1+M2 + WARNING docstring
- [tests/test_framework_search/test_indexer_mrl.py](../../tests/test_framework_search/test_indexer_mrl.py) — существующие тесты (9 кейсов), нужно +2 для alias-recreate
- [mypy-baseline.txt](../../mypy-baseline.txt) — текущий baseline (1920 строк)

---

## Решение (2026-05-17)

**ОТЛОЖЕНО до отдельной follow-up сессии.** Триггеры для re-evaluation:
1. План использовать `--recreate` против aliased коллекции вручную
2. Новый сбой mypy ratchet блокирует unrelated commit work
3. Запланирована периодическая cleanup-сессия для tech-debt
4. Подготовка Pull Request — почистить перед merge в main
