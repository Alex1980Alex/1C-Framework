# ADR-011: Модель синхронизации курируемой памяти и Event Store с авто-store'ами

**Дата:** 2026-06-12
**Статус:** accepted
**Исследование:** [../cache/curated-memory-event-store-sync-2026.md](../cache/curated-memory-event-store-sync-2026.md)

## Контекст

Карта 27.12 делит память на оркестрируемые «5 колонок» (memory-ai, vector-memory,
skill-learning, pdf-docs, LinkRegistry) и блок «ОТДЕЛЬНО»: курируемая память
(`MEMORY.md` + `memory/*.md`, ручной write-gate) и Event Store (`events.jsonl`+`events.db`).
Вопрос: должна ли между блоками существовать синхронизация-репликация, и какой
канал переноса знаний легитимен.

## Решение

Репликация между блоками — **non-goal**. Синхронизация существует ровно в трёх формах:

1. **Read-time merge** — `memory-first-hook` сливает md-плечо (курируемый слой)
   с sqlite/qdrant-плечами в один RRF на каждый промпт; recall-reminder инжектит
   `.md`-записи. Данные не копируются — сливаются выдачи. [own]
2. **Manual promotion (HITL write-gate)** — store→канон только через человека.
   Индустриальный паттерн «holding area → human review → promotion into canonical
   base»; «HITL as write gate is quality control when the writer is a stochastic
   process» [web: agentmemory lessons, GitHub Copilot agentic memory]. Входящий
   конвейер: SessionStart-хук `memory-curation-candidates-on-start.py` (R1) —
   баннер зрелых паттернов (eff_conf>=0.85, apps>=5), не покрытых `memory/*.md`;
   запись создаёт только человек/подтверждение. Записи несут **citations**
   (file:line / commit) — verify-at-read дешевле (паттерн Copilot memory) [web].
3. **Event-эмиссия** — orchestrator-mediated мутации store'ов порождают события
   (write-through, односторонне). Event store = auditability/replay/debugging
   («event store, не stream, нужен для AI-auditability» [web: AxonIQ]);
   **восстановление store'ов из событий — non-goal** (JSONL не concurrent-safe
   между процессами, ADR-V wire-minimal; индустрия использует replay для
   аудита/отладки, не как primary recovery в agent memory) [web+own].

Конфликт-резолюция: канон = курируемый слой + текущий код; store-запись проигрывает.

## Последствия

### Положительные
- Trust-градиент канона сохранён (автогенерат не загрязняет курируемый слой).
- Соответствие доминирующей практике 2026 (mem0/Letta/Copilot: tiered + HITL-gate).
- Курируемый слой изолирован от сбоев store'ов и governance (TTL/forget его не трогают).

### Отрицательные
- Перенос знаний требует человеческого действия (смягчено R1-баннером).
- Двойное хранение зрелого знания (паттерн + .md) — принято осознанно: уровни
  доверия разные.

## Альтернативы

- **Авто-репликация .md↔Qdrant** — отклонена: ломает write-gate, загрязняет канон.
- **Event-sourcing восстановление store'ов** — отклонена: не concurrent-safe,
  не практикуется в agent-memory системах, спрос отсутствует.
- **Автозапись зрелых паттернов в memory/*.md** — отклонена: ровно то, от чего
  write-gate защищает (стохастический писатель в каноне).

## Связанные файлы

- `.claude/hooks/memory-curation-candidates-on-start.py` (R1)
- `.claude/hooks/memory-first-hook.py` (md-плечо)
- `docs/framework documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md` (блок «ОТДЕЛЬНО»)
- `src/memory/infrastructure/event_bus.py`, `event_store.py`
