# Реализация

## Изменения

| Файл | Что |
|---|---|
| [`shared/invocation_logger.py`](../../.claude/hooks/shared/invocation_logger.py) | Параметр `in_repo: bool \| None`; ключ пишется только когда не `None` (паттерн `duration_ms`) |
| [`tool-invocation-logger.py`](../../.claude/hooks/tool-invocation-logger.py) | `_PROJECT_ROOT` + `_target_in_repo()`; проводка в `log_invocation` |
| [`pipeline-protocol-stop.py`](../../.claude/hooks/pipeline-protocol-stop.py) | `_session_writes_and_start`: внешние записи не считаются правкой |

Путь в лог **не попадает** — только бит; контракт `_args_fingerprint` («пути/секреты не утекают») цел.

## Правка по вердикту ревьюера (PASS + 2 ноты)

**Нота 1 закрыта — ложный allow.** Block-запись бита не несёт (её пишет `BaseHook`-автолог, не tool-logger). Первая редакция пропускала внешнюю строку через `continue` **до** сопоставления, из-за чего блок от отклонённого ВНЕШНЕГО `Write` оставался бесхозным и мог «оправдать» реальную правку в репозитории, попавшую в окно `BLOCK_MATCH_SEC=5с`.

Лечение: внешние записи участвуют в хронологическом сопоставлении и **забирают свой блок**, оставаясь при этом «не правкой». Проход по времени — блок достаётся тому вызову, к которому относится.

**Нота 2 принята как известное ограничение.** `realpath` не приводит UNC-путь (`\\server\share\repo\…`) или `subst`-псевдоним к реальному корню ⟹ правка через сетевой путь получила бы `in_repo=False`. В текущей конфигурации (локальный путь) недостижимо; лечение при появлении такого режима — сравнение по `st_dev`/`st_ino`.

## Проверки

- **18 unit** ([`test_pipeline_signal_outside_repo.py`](../../tests/unit/test_pipeline_signal_outside_repo.py)), **396** в затронутых наборах (gate-parity, harness, policies, blocked-write, git-signal, tool-obs) — зелёные.
- **Live-контракт** (юнит-фикстура формы payload лжёт): прогон настоящего хука через pipe — memory-путь ⟶ `in_repo: false`, файл проекта ⟶ `true`. Тестовые строки вычищены из продового лога (класс [[feedback-test-log-pollution-enforcement-hole]]).
- **Саботаж ×3:** откат пропуска ⟶ 2 красных; удаление проводки ⟶ 1 красный (`test_logger_actually_passes_the_bit`); откат правки по ноте ревьюера ⟶ 1 красный. Каждый краснит ровно целевое.

⚠ **Найдено саботажем:** до добавления `test_logger_actually_passes_the_bit` удаление проводки `in_repo=_target_in_repo(...)` не роняло НИ ОДНОГО теста — фикс был бы мёртв при зелёном наборе. Тот же класс, что Р4 прошлого ревью llm-rotation.
