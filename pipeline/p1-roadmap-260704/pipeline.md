# Pipeline — P1 роадмапа 260704 (приоритет: код → doc-drift)

**Дата:** 2026-07-04

## Планирование
P1 = дрейф счётчиков + legacy + пути по ~50 док-файлам (5 доменов) + ОДИН реальный
code-форк: Langfuse. Приоритет пользователя: сначала код, потом доки.

## Дизайн
Код=истина. Единственная code-правка — Langfuse: код на v2 API, окружение v4.6.1 →
трейсинг молча мёртв. Решение пользователя (AskUserQuestion): **мигрировать на v4 API**.
Остальное — doc-drift (счётчики по факту кода/конфига), дозачистка доменными агентами.

## Кодирование (Langfuse v4 migration — DONE)
- `callbacks/langfuse/langfuse_callback.py` — переписан: subclass нативного
  `langfuse.langchain.CallbackHandler`; ручные v2 on_* удалены (наследуются от v4);
  интерфейс `(enabled,user_id,session_id,creds)` + `_enabled`/`_resolve_credentials` сохранён.
- `observability/tracer.py` — `.span()`→start_observation(span)+update+end;
  `.score()`→create_score; `.generation()`→start_observation(generation)+update+end.
- `pyproject.toml` — `langfuse>=2.0` → `>=4.0,<5.0` (реальность = 4.6.1).
- `observability/langfuse_setup.py:emit_observation` — уже был на v4, не тронут.

## Тестирование / верификация
- compile OK; grep остаточных `_client.span/.generation/.score` = 0.
- import+construct: LangfuseCallbackHandler = валидный BaseCallbackHandler, on_* унаследованы,
  события graceful no-op без кредов.
- `tests/unit/observability/test_langfuse_setup.py` — 8 passed.
- code-verify reviewer (bug-fix-validation) — PASS.

## Doc-drift (следующая волна)
Канонические счётчики (свежие, по факту): скиллы 97, бандлы 52, config v9, домены 8,
хуки 97 файлов / 99 регистраций. auto-git-save threshold=1 (не 3), pip-audit без schedule:,
pymorphy3 (не thefuzz). Правки — доменными агентами, код=истина.
