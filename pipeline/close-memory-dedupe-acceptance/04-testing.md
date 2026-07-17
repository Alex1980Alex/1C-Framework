# 04 — Верификация

## Acceptance §5 роадмапа 260716 — все пункты закрыты

| # | Критерий | Статус | Как проверено |
|---|---|---|---|
| §5.1 | битая точка → инструменты живы, точка в `items_skipped` | ✅ (пин) | `test_memory_p1_resilience.py`, `test_pattern_type_contract.py` |
| §5.2 | мусорный `pattern_type` у писателей → только coerced | ✅ (пин) | `test_pattern_type_contract.py` |
| **§5.3** | **0 дублей hash, 0 без content_hash, 0 вне enum** | **✅ NEW** | live: re-dry-run `dup_groups=0`; verify-скрипт 0/0/0 |
| §5.4 | `merge --apply` не теряет полей | ✅ (пин) | `test_memory_p1_resilience.py` (PatternRecord.extra) |
| **§5.5** | `sources_failed` пусто при живом Qdrant | **✅** | live: `unified_search` → `sources_failed=[]`, 3 плеча, 10 рез. |

## Live-верификация (in-process, `scratchpad/verify_dedupe_acceptance.py`)

```
=== §2 data cleanliness ===  total points: 151
[PASS] §2 pattern_type all in enum       — 0 outside
[PASS] §2 content_hash present on all     — 0 missing
[PASS] §5.3 no content_hash duplicates    — 0 dup
=== §5.5 orchestrator ===
[PASS] §5.5 unified_search sources_failed empty — failed: []
       unified results: 10, sources: [memory-ai, vector-memory, skill-learning]
=== плечо == тул (M4) ===
[PASS] плечо == тул — tool count=10 skipped=0 == arm count=10, contents identical
=== link integrity ===
[PASS] link_registry 0 dangling (learned_patterns ends)
RESULT: ALL PASS
```

`плечо == тул` (M4/P1.4) подтверждает: после дедупа vector-плечо `unified_search` и тул
`search_patterns` зовут ЕДИНУЮ `search_pattern_points` → одни точки в одном порядке.

## Регресс (unit)

`test_dedupe_learned_patterns.py` (7) + `test_pattern_type_contract.py` (41) +
`test_memory_p1_resilience.py` (48) = **96 passed** (2.27s). Правок кода нет → регрессий нет.

## Обратимость

Бэкап `learned_patterns_20260717_225637.json` (154 pts + 47 links + векторы) проверен на
целостность. Повторный dry-run: `dup_groups=0` (идемпотентность — повторный `--apply` = no-op).
