# 01 — Планирование: P0 hardening памяти

Источник требований: [роадмап 260716 §4 P0](../../docs/roadmap/260716_ROADMAP_MEMORY_PAYLOAD_HARDENING.md).
Аудит-артефакт: [audit-memory-subsystem](../audit-memory-subsystem/pipeline.md).

## Задача

Закрыть инцидент (`'requirements' is not a valid PatternType` роняет vector-плечо
`unified_search`) и весь его класс: payload из store читается как доверенный вход.

## Инвариант

**Payload = недоверенный вход.** Писатели нормализуют перед записью; читатели
коэрсят защитно ВСЁ РАВНО (старые данные + любой будущий необновлённый писатель +
админ-скрипты, пишущие напрямую). Одна битая точка = skip с логом, НЕ смерть
инструмента.

## Затрагиваемые файлы

| Файл | Роль |
|---|---|
| `src/memory/vector_memory/models.py` | коэрсер + safe-парсеры (контракт, stdlib-only) |
| `src/memory/vector_memory/confidence.py` | `_resolve_state`/`should_archive` толерантны |
| `src/memory/vector_memory/server.py` | `_pattern_from_payload` + per-item try в 3 циклах |
| `src/memory/maintenance/forget_gate.py` | `plan_forget` per-item |
| `src/memory/orchestrator/memory_orchestrator.py` | vector-плечо per-item; 2 writer-ветки |
| `src/memory/skill_learning/server.py` | схема + handler `capture_pattern` |
| `.claude/hooks/shared/pattern_harvest.py` | `_build_payload` (главный канал заражения) |
| `scripts/migrate_pattern_types.py` (новый) | миграция Qdrant + силоса |
| `tests/unit/test_pattern_type_contract.py` (новый) | регресс |

## Порядок

P0.1 коэрсер → P0.2 read → P0.3 writers → P0.4 миграция → P0.5 тесты/verify.
Сначала read (снимает симптом на текущих данных), потом write (убирает источник),
потом миграция (чистит хвост) — каждый шаг самостоятельно ценен.
