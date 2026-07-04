# ADR — Q1 (§26 P1 D1.3): `experience_embeddings` / `conversation_memory` — наполнить или deprecate?

> **Дата:** 2026-06-03 · **Статус:** accepted · **Родитель:** [260602 §26 P1 D1.3 / Q1](260602_ROADMAP_MEMORY_INGESTION_SYNC.md#L93) · **Тип:** roadmap-scoped ADR (блокер закрытия P1)
>
> Research: code-grounded inventory (live 2026-06-03) + переиспользование attributed WebSearch из [260602 §3](260602_ROADMAP_MEMORY_INGESTION_SYNC.md#L43) (mem0 / Letta / Zep / Generative Agents / CraniMem, 2026-06-02).

---

## Решение (TL;DR)

**DEPRECATE обе коллекции** `experience_embeddings` и `conversation_memory`. Первичное основание — их предполагаемую роль (episodic experience + conversation recall) **уже полностью покрывает** принятый §26-конвейер **episodic (`memory_ai.db`) → reflection (P2) → semantic (`learned_patterns`) → wiki**, keyed by `content_hash`, bounded `ForgetGate`. Альтернатива «наполнить» отклонена отдельно — она не нейтральна, а **net-negative** (плодит cross-store дубликаты + unbounded raw-turn рост). Не держать «0 writers без объяснения».

---

## Контекст

§26 ставит диагноз ([260602 §1](260602_ROADMAP_MEMORY_INGESTION_SYNC.md#L11)): машинерия retrieval/governance богатая, но **нечем кормить** — `experience_embeddings`/`conversation_memory` = **0 writers**. D1.3/Q1 требует формального выбора **ПЕРЕД** закрытием P1: либо вшить writer, либо формально deprecate.

### Code-grounded инвентаризация (live 2026-06-03)

| Факт | Подтверждение |
|---|---|
| Обе коллекции = **0 точек** | CLAUDE.md §«Qdrant коллекции»; `experience_embeddings/conversation_memory (0, ready for auto-populate)` |
| **0 writers** ни у одной | grep по репо: ни одного `upsert`/`save` в эти коллекции; есть лишь невшитый stub `experience-embedder.py` |
| Обе **читаются** §24-surfacing'ом как arms | [`memory-first-hook.py:105-110`](../../.claude/hooks/memory-first-hook.py#L105) `SEMANTIC_COLLECTIONS` → arms `experience`/`conversation`, веса 0.5 ([:94-100](../../.claude/hooks/memory-first-hook.py#L94)) |
| Каждый surfacing-вызов делает **2 Qdrant-запроса, всегда возвращающих `[]`** | `search_qdrant` фанит по всем `SEMANTIC_COLLECTIONS` → RRF; пустые коллекции = no-op arms + чистый latency-tax |
| `MemoryCube` **НЕ имеет проекции** в эти store | [`memcube.py`](../../src/memory/orchestrator/memcube.py): проекции только `to_ai_memory_row`/`to_vector_memory_payload`/`to_skill_learning_record`/`to_wiki_page` — ни `to_experience_*`, ни `to_conversation_*` |
| Naming-collision: класс `ConversationMemory` ≠ Qdrant-коллекция | [`src/pdf_framework/agents/memory/conversation.py`](../../src/pdf_framework/agents/memory/conversation.py) — chat-API thread history, пишет в **SQLite** `data/conversations.db`; к пустой Qdrant-коллекции отношения не имеет |

**Ключевое наблюдение:** обе коллекции — рудимент Phase 8/9 «эмбеддим всё». §26-архитектура ([260602 §4](260602_ROADMAP_MEMORY_INGESTION_SYNC.md#L52)) их **не содержит** в data-flow диаграмме: источники = feedback-drafts / session-lessons / skill-confirmed → harvester → `MemoryCube` → `learned_patterns`; консолидация P2 = `memory_ai.db` → reflect → `learned_patterns`. Узлов «experience» и «conversation» в плане нет — они осиротели от предыдущего дизайна.

---

## Разбор на реальном примере

Возьмём **реальный** повторяющийся факт из курируемой памяти — `feedback_1c_read_attribute_bsp`: *«не `Ссылка.Реквизит`, а `ОбщегоНазначения.ЗначениеРеквизитаОбъекта` — код-ревью заказчика, повторял 2×»*. Проследим один и тот же факт через обе альтернативы.

### Путь A — ПОПУЛИРОВАТЬ (вшить writers в обе коллекции) — отклонён

Один факт после двух сессий код-ревью порождает:
- **`conversation_memory`**: сырые turn'ы (реплика ревьюера + мой ответ) × 2 сессии ≈ **4 вектора**;
- **`experience_embeddings`**: session-summary эпизода × 2 сессии = **2 вектора**;
- **`learned_patterns`**: дистиллированный паттерн = **1 вектор**;
- плюс SQLite-строка `memory_ai.db` + курируемая `MEMORY.md` запись.

Итог: **~7 near-identical векторов в 3 Qdrant-коллекциях** для одного факта. При surfacing'е RRF обязан дедупить эти 7 хитов — а сырые turn'ы хэшируются **иначе**, чем дистиллированный паттерн, так что `content_hash`-dedup спасает лишь частично. Это **ровно** болезнь «один факт = независимые копии в каждом store», которую §26 §1 называет диагнозом, а §26 P3 (cross-store dedup + `conflict_resolver`) потом героически лечит. То есть популяция этих коллекций не нейтральна — она **активно создаёт** ту проблему, ради устранения которой существует §26. Анти-цель.

Дополнительно: хранение сырых turn'ов вектора-в-вектор — это classic unbounded-growth, против которого предостерегает CraniMem / «Episodic Memory is the Missing Piece» ([260602 §3](260602_ROADMAP_MEMORY_INGESTION_SYNC.md#L49)); mem0 и Generative Agents **дистиллируют**, а не дампят сырьё.

### Путь B — DEPRECATE (выбранный)

Тот же факт:

```
сырые turn'ы (эфемерны, в transcript)
  └► session-memory-save (Stop) ──► memory_ai.db session_summary   (episodic, 1 строка/сессия)
        └► P2 reflection: кластеризует 2 повтора по триггеру ──► 1 learned_patterns паттерн
              (content_hash-keyed, §22 confidence-gate)
              └► P3 PROMOTED_TO link ──► wiki   (связь, не копия)
```

**Один факт → один канонический cube → связи, не копии.** Surfacing фанит по `learned_patterns` (dense+lexical) + SQLite + `skill_library` + wiki — **без пустых arms, без сырого turn-шума**. Факт всплывает один раз.

> Что «find past discussion» уже работает БЕЗ отдельной коллекции — видно прямо в этой сессии: инжектированный `[MEMORY CONTEXT]` поднял `[SQLite|...] session_summary: "Session 2026-05-30..."` / `"Session 2026-06-03..."`. Слой `memory_ai.db` (SQLite, weight 0.30) уже отвечает на «о чём мы говорили раньше». Отдельный raw-turn vector-store **дублировал бы это с худшим signal-to-noise.**

**Вывод примера:** существующего episodic+semantic конвейера **достаточно** для роли обеих коллекций (это и есть первичное основание deprecate); а популяция вдобавок **net-negative** — создаёт дубликаты, которые §26 P3 затем должен вычищать. Обе ветки рассуждения ведут к одному выбору.

---

## Последствия

### Положительные
- §26-конвейер остаётся single-source: episodic→semantic→wiki, `content_hash`-keyed. Роль покрыта без новых сущностей.
- Убирается 2 no-op Qdrant-запроса на **каждый** prompt (latency-win в hot-path surfacing).
- P3 cross-store dedup не получает рукотворных дубликатов.
- RRF-fusion проще: 3 arm'а (`skill`, `pattern_dense`, `pattern_lexical`) + SQLite/wiki-слои вместо 5 (2 из которых мёртвые).
- Карта 27.12 перестаёт обещать «ready for auto-populate» без срока поставки (документ-долг закрыт).
- `MemoryCube` НЕ нужно расширять двумя новыми проекциями (`to_experience_*`/`to_conversation_*`) — меньше surface area.

### Отрицательные / риски
- Если кто-то отдельно реализует §32.4 hooks (stub `experience-embedder.py`) — он упадёт на отсутствующей коллекции. **Митигация:** удалить stub в составе deprecation; зафиксировать в §32.4 roadmap, что пункт superseded этим ADR.
- Потеря гипотетической семантики «поиск по сырым диалогам». **Оценка:** низкий риск — роль покрыта `memory_ai.db` session_summary + `learned_patterns`; сырьё = шум, не сигнал.
- Reversibility: коллекции 4096d легко пересоздаются (`phase8_recreate_reindex.ps1` шаблон) если решение когда-либо superseded.

---

## Реализационные шаги (выполнить в составе P1 close, reversible)

1. **Surfacing**: убрать `("experience_embeddings", "experience")` и `("conversation_memory", "conversation")` из `SEMANTIC_COLLECTIONS` ([`memory-first-hook.py:105`](../../.claude/hooks/memory-first-hook.py#L105)); удалить ключи `experience`/`conversation` из `SURFACE_RRF_WEIGHTS` ([:94](../../.claude/hooks/memory-first-hook.py#L94)) и arms-словаря в `search_qdrant`.
2. **Тест**: убрать обе из `KNOWN_COLLECTIONS` ([`tests/integration/test_memory_first_hook.py`](../../tests/integration/test_memory_first_hook.py)).
3. **Config**: вычистить упоминания в `infra/lazy-mcp/config/registry.yaml`, `.mcp/full.json`, `.mcp/lazy-mcp-config.json`, `.claude/skills/qdrant-operations/SKILL.md`, `.claude/commands/pdf-search.md`.
4. **Qdrant**: удалить пустые коллекции `experience_embeddings` + `conversation_memory` (0 точек → потерь нет; snapshot перед delete по гайдрелу §6).
5. **Stub**: удалить невшитый `experience-embedder.py`; пометить §32.4.1/§32.4.2 в [260426 Phase 8 roadmap](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md) как **superseded by этим ADR**.
6. **Карта**: привести [27.12 Memory Systems Map](../framework%20documentation/5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md) в соответствие — убрать обе из списка живых store, добавить строку «deprecated 2026-06-03 (ADR Q1), роль → episodic+semantic».
7. **НЕ трогать** класс `ConversationMemory` (SQLite chat-history) — он легитимен и используется chat-API; deprecate касается только одноимённой Qdrant-коллекции (зафиксировать в commit-message во избежание путаницы).

> Сам ADR (этот файл) = блокер закрытия P1. Шаги 1-7 — часть P1-execution; выполняются под guardrails §26 §6 (reversible — это удаление мёртвого кода, не поведенческий флаг).

---

## Альтернативы (отклонены)

- **A. Полная популяция обеих коллекций** — отклонено: плодит cross-store дубликаты (см. «Путь A»), нарушает single-source принцип §26, добавляет unbounded raw-turn рост. Прямо противоречит цели §26.
- **A′. Популировать только `experience_embeddings`** (как «эпизодический» вектор-store) — отклонено: дублирует `memory_ai.db` session_summary, который уже surface'ится как SQLite-слой; добавляет вторую episodic-сущность вместо консолидации в semantic.
- **C. Оставить как есть (0 writers, читаем впустую)** — отклонено: вечный latency-tax (2 пустых запроса/prompt) + документ-долг «ready for auto-populate» без срока; D1.3 явно запрещает «мёртвые коллекции без объяснения».

---

## Связанные файлы

- [`memory-first-hook.py`](../../.claude/hooks/memory-first-hook.py) — `SEMANTIC_COLLECTIONS`, `SURFACE_RRF_WEIGHTS`, `search_qdrant`
- [`memcube.py`](../../src/memory/orchestrator/memcube.py) — отсутствие experience/conversation проекций (подтверждение)
- [`tests/integration/test_memory_first_hook.py`](../../tests/integration/test_memory_first_hook.py) — `KNOWN_COLLECTIONS`
- [`src/pdf_framework/agents/memory/conversation.py`](../../src/pdf_framework/agents/memory/conversation.py) — SQLite-класс (НЕ затрагивается)
- [260602 §26 P1 D1.3 / Q1](260602_ROADMAP_MEMORY_INGESTION_SYNC.md) · [260426 Phase 8 §32.4](260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md)
