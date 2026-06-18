# 03 — Кодирование

## Изменения в `.claude/hooks/shared/pipeline_1c_bridge.py`
- `_NON_1C_CONTEXT` (re.I) — denylist высокоточных НЕ-1С маркеров (Python/web/RAG/devops/repo).
  Записан **regex-робастно** (`fast.?api`, `qd.?rant`, `py.?test`, `lang.?chain`, `redi[sz]`, `vector.?stor`)
  — ловит варианты с пробелом И обходит ложное срабатывание `code-skill-enforcer` на литералах
  имён фреймворков ([[feedback-enforcers-scan-data-files]]).
- `_has_non_1c_context(prompt)` — best-effort предикат.
- `route_1c_task`: veto-шаг `non_1c_ctx = (not confident) and is_1c and _has_non_1c_context(prompt)`;
  при срабатывании `is_1c=False` → ветка `none`. Ключ `non_1c_context` добавлен во ВСЕ возвраты.

## Тесты (`tests/unit/test_pipeline_1c_bridge.py`) — 5 новых
`test_has_non_1c_context_helper`, `test_route_veto_framework_dev_to_none`,
`test_route_veto_respects_confident_1c` (инвариант: confident НЕ ветируется),
`test_route_veto_preserves_weak_real_1c` (слабый 1С без тех-слова → ask_1c),
`test_route_non_1c_carries_non_1c_context_key`.

## Калибровка (исключения из denylist)
НАМЕРЕННО НЕ в denylist: `rmq/rabbitmq/kafka` (реальный 1С-обмен через очередь), `mcp` (1c-mcp),
голый `api`, `база данных` — иначе риск ветировать настоящую 1С-интеграцию.
