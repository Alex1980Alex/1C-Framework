# Пайплайн (trivial): фикс BLOCKER memory_ttl_cleanup

Источник: `/review #77` нашёл BLOCKER. Пользователь: «реализуй».

## 1. План
Починить затенение переменной `removed` в `MemoryOrchestrator.memory_ttl_cleanup`
(`src/memory/orchestrator/memory_orchestrator.py`) + регресс-тест, который ловит баг.

## 2. Дизайн
- **Корень:** внутри цикла `removed = self._link_registry.delete_links_for_entity(eid)`
  (`-> int`) перезатирал `removed`-ledger (list), а `return` делает `len(removed)`
  → `TypeError: object of type 'int' has no len()` ПОСЛЕ мутации store'ов.
- **Фикс:** переименовать внутреннюю переменную в `links_removed` (поведение
  `links_removed`-репорта сохранено).
- **Почему баг прошёл тесты:** существующие F9-тесты (`_orch(with_ttl=True)`)
  оставляют `_link_registry=None` → строка падает AttributeError ДО присваивания →
  `removed` не затирается. Регресс-тест **подключает** stub-LinkRegistry → триггерит.
- ADR не нужен (bugfix).

## 3. Реализация
- Edit `memory_orchestrator.py` (строки ~1485-1487): `removed` → `links_removed` + коммент.
- Add `tests/unit/test_governance_wiring.py::test_ttl_cleanup_link_cleanup_does_not_clobber_ledger`.
- Коммит `943a37f0a` (+42/-3, 2 файла; auto-save preempt поглощён `--amend`).

## 4. Тест (red → green)
- **Pre-fix:** регресс падает `TypeError: object of type 'int' has no len()`
  на `memory_orchestrator.py:1502` — баг подтверждён в runtime, тест его ловит.
- **Post-fix:** `pytest tests/unit/test_governance_wiring.py` → **9 passed** (8 старых + новый).
- Правка хирургическая (rename в одной функции) → широкого влияния нет.
- ⚠ MCP-side: для эффекта в живом `memory-orchestrator` нужен `/mcp reconnect`
  (тест прогнан против кода напрямую — reconnect для верификации не требуется).
