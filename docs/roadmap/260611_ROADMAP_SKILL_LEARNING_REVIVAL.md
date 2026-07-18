# 260611 — Roadmap: оживление skill-learning (JSONL pending/saved/rejected) как рабочего контура Claude

> Статус: IMPLEMENTED 2026-06-12 (P0–P3 код, P4 — acceptance-наблюдение 2 недели) · Создан: 2026-06-11 · Источник: анализ блока `skill-learning` карты
> [27.12 §10](../framework%20documentation/5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md)
> Связанные: [260609 P1 write-contract](260609_ROADMAP_MEMORY_PIPELINE_HARDENING.md), [260611 governance wiring](260611_ROADMAP_MEMORY_GOVERNANCE_WIRING.md), §26 P2 D2.2 (harvest confirmed)

## 1. Проблема

Подсистема skill-learning (`data/skill_learning/*.jsonl`, MCP `skill-learning`, 7 tools)
архитектурно готова (write-contract P1.3, harvest-мост §26 D2.2, адаптер в `unified_search`),
но **мертва как рабочий контур**: фактическое состояние на 2026-06-11 — pending=0, saved=1,
rejected отсутствует. Claude в ходе работы туда **не пишет** и оттуда **не читает**:

- **Вход не подключён**: ни один хук/протокол не вызывает `capture_pattern`; паттерны идут
  напрямую в `learned_patterns` (Qdrant) через `save_pattern`/харвестеры, минуя карантин.
- **Выход не виден**: `memory-first-hook` (surfacing на каждый промпт) слои sqlite/qdrant/md —
  skill-learning не читает; единственный читатель `patterns.jsonl` — keyword-overlap плечо
  `unified_search` (вызывается редко) и Stop-харвест.
- **Гигиена**: `route_and_save` пишет мимо pending (карантин обходится); rejected — тупик
  (не участвует в dedup → отклонённое можно захватить заново); `_write_jsonl` не атомарен;
  `learning_stats.json` только инкрементится (дрейф от реальности).

Целевая модель: **pending/saved/rejected = карантинный конвейер паттернов-кандидатов,
в который Claude пишет по ходу работы (вход) и состояние которого видит на старте сессии
и в surfacing (выход); confirm = пропуск в `learned_patterns` (§22 confidence), reject =
перманентный негативный сигнал.**

## 2. Фазы

### P0 — Гигиена хранилища (фундамент, без новых потоков)

| # | Задача | Файлы | Критерий приёмки |
|---|--------|-------|------------------|
| P0.1 | Атомарная перезапись pending: `_write_jsonl` через tmp + `os.replace` (паттерн post-indexing-analyzer state) | `src/memory/skill_learning/server.py` | kill -9 посреди confirm не теряет pending |
| P0.2 | Rejected как негативный dedup: `_existing_hashes()` включает `rejected_patterns.jsonl`; повторный capture отклонённого → `action=dup_rejected`, `record_ingest("dup", reason="rejected")` | `server.py` | re-capture отклонённого контента не создаёт pending |
| P0.3 | Stats derive-on-read: `get_learning_stats` пересчитывает из файлов (как `health_check`), `learning_stats.json` — кэш, не источник истины | `server.py` | total == фактическим строкам saved |
| P0.4 | `route_and_save` target=skill-learning → пишет в **pending** (не в saved) с `metadata.routed:true`; либо явный `auto_confirm` флаг от вызывающего | `src/memory/orchestrator/memory_orchestrator.py:1905` | карантин не обходится молча |

⚠ Всё MCP-side → `/mcp reconnect` после правок ([[feedback-mcp-stale-code-reconnect]]).

### P1 — ВХОД: Claude пишет в ходе работы

| # | Задача | Механизм |
|---|--------|----------|
| P1.1 | **Протокольный capture**: в SKILL.md `task-protocol` (шаг Verify) и `code-verify` добавить явный шаг — после verify PASS нетривиальной задачи Claude вызывает `mcp__skill-learning__capture_pattern` (pattern_type из факта работы: workflow-pattern / bsl-pattern / error-fix; `evidence_sources=[{session, files}]`, `require_confirmation=true`) | инструкция-уровень, 0 кода |
| P1.2 | **Авто-capture lessons → pending**: Stop-бридж (расширение `patterns-harvester.py` или новый хук) направляет session-lessons/`data/memory_drafts/` кандидаты НЕ напрямую в Qdrant, а через `capture_pattern` (pending) — карантин становится единственной точкой входа авто-захвата. ADR-вопрос: менять ли существующий маршрут drafts→`learned_patterns` (сейчас работает) — предлагается **дополнить**, не заменять: drafts с confidence <0.8 → pending, ≥0.8 → как сейчас | `.claude/hooks/` + `shared/pattern_harvest.py` |
| P1.3 | **Негативный вход**: при явной коррекции пользователем ранее применённого паттерна — `capture_pattern(confidence=0.3)` + немедленный `reject_pattern` (фиксация анти-паттерна в rejected-silo, который после P0.2 блокирует повторный захват) | инструкция-уровень |

### P2 — ВЫХОД: Claude читает в ходе работы

| # | Задача | Механизм |
|---|--------|----------|
| P2.1 | **SessionStart-баннер**: новый лёгкий хук `skill-learning-pending-on-start.py` — `[SKILL-LEARNING] pending=N (oldest 12d): <top-3 names>` при N>0; напоминание о модерации (паттерн gh-notif-intake) | SessionStart, чтение JSONL <50ms, fail-soft |
| P2.2 | **Surfacing-плечо**: в `memory-first-hook` добавить дешёвый lexical arm по `patterns.jsonl` + `pending_patterns.jsonl` (пометка `status=pending` в выдаче) — RRF-слияние с остальными плечами; кандидат виден ДО подтверждения (early signal) | `.claude/hooks/memory-first-hook.py`; opt-out env |
| P2.3 | **Адаптер-поиск**: `SkillLearningSearchAdapter` — casefold + простая RU-нормализация (стемминг по top-K salient-логике P1.2 cache-key) вместо точного word-overlap; кириллические морфоформы матчатся | `memory_orchestrator.py:290` |

### P3 — Цикл модерации (pending не должен гнить)

| # | Задача | Механизм |
|---|--------|----------|
| P3.1 | **Модерация в maintenance-cadence**: job `review_pending` в `scripts/memory_maintenance.py` — pending старше TTL (30d) без подтверждения → auto-reject (`reason=ttl_expired`); отчёт в dashboard | §26 P4 каденс, dry-run default |
| P3.2 | **Confirm → немедленный harvest**: `handle_confirm` после записи в saved детачит harvest этого паттерна в `learned_patterns` (детерминированный `content_hash.point_id` — идемпотентно с Stop-харвестом) + epoch.bump → surfacing видит сразу | `server.py` + `shared/pattern_harvest.py` |
| P3.3 | **Мост в SKILL.md (опция)**: confirmed паттерн с накопленным §22 effective_confidence ≥0.85 и application_count ≥5 → draft через `doc-to-skill` (аналог WikiPromoter, `promoted_to` link) | отдельный ADR, после P0–P2 |

### P4 — Наблюдаемость и приёмка

- `skill_learning` уже эмитит `record_ingest` → проверить, что `memory_observability_{query,report}.py` видят store в views (fact-trace по `content_hash` должен тредить capture→confirm→harvest→reinforce).
- **Acceptance (2 недели после P1/P2)**: ≥10 capture; pending median age <7d; ≥1 reject;
  confirmed паттерны всплывают в surfacing-логе (`memory-first-surfacing.log` arm=skill-learning);
  `dup`/`dup_rejected` в ingest-логе ≠ 0 (dedup работает).

## 3. Порядок и оценка

P0 (≤0.5d, один файл + 1 строка orchestrator) → P1.1+P2.1 (быстрые победы, ≤0.5d) →
P2.2+P2.3 (1d) → P1.2 (ADR + 1d) → P3 (1d) → P4 (наблюдение). Учитывать
[[project-roadmap-audit-pattern]]: инвентаризация перед каждой фазой — часть уже могла
быть сделана смежными roadmap'ами.

## 4. Риски

- **Дублирование контуров**: skill-learning (паттерны-кандидаты) ≠ `skill_library` (индекс SKILL.md) ≠ `learned_patterns` (подтверждённая семантика). P1.2/P3.2 должны опираться на общий `content_hash` — иначе один факт разъедется по трём store'ам мимо `cross_store_sync`.
- **JSONL concurrency**: surfacing-чтение (P2.2) + Stop-харвест + MCP-запись на одних файлах — P0.1 обязателен ДО P2.2; версионирование на skill-learning НЕ распространять (ADR-V).
- **Шум в pending**: без P3.1 авто-capture (P1.2) превратит pending в свалку — TTL-reject обязателен в том же релизе.

## §18 Progress Log

| Дата | Событие | Детали |
|------|---------|--------|
| 2026-06-11 | Roadmap создан | Анализ блока: вход/выход мертвы (saved=1, pending=0); карта фаз P0–P4 |
| 2026-06-12 | P0 DONE | `server.py`: атомарный `_write_jsonl` (tmp+`os.replace`), rejected в `_existing_hashes` → `dup_rejected`+`record_ingest(reason="rejected")`, stats derive-on-read (дрейф 2→1 устранён); `route_and_save` → pending (`metadata.routed:true`) + dedup vs 3 silo + `auto_confirm` opt-out (`_find_jsonl_hash` helper). Smoke оба PASS |
| 2026-06-12 | P1.1+P1.3 DONE | SKILL.md `task-protocol` шаг 6 CAPTURE (после verify PASS, medium/complex) + `code-verify` (после PASS — capture блок); негативный вход: capture(0.3)+reject. Инструкция-уровень, 0 кода |
| 2026-06-12 | P2.1 DONE | Хук [`skill-learning-pending-on-start.py`](../../.claude/hooks/skill-learning-pending-on-start.py) (SessionStart, timeout 3s, fail-soft, opt-out `SKILL_LEARNING_PENDING_DISABLE=1`), регистрация в settings.json. Smoke: пустой→silent, 2 pending→баннер с oldest-age и top-именами |
| 2026-06-12 | P2.2+P2.3 DONE | `memory-first-hook`: плечо `skill_learning` (weight 0.4, saved+pending, pending ×0.7 damp + метка `[pending]`/`sl/pending`, opt-out `MEMORY_SURFACE_SKILL_LEARNING_DISABLE=1`); `SkillLearningSearchAdapter` → `_sl_tokenize` (casefold + RU-суффиксы) — морфоформы матчатся (smoke: exact-overlap 1 общий токен → normalized match) |
| 2026-06-12 | P1.2 DONE | `pattern_harvest.py`: `HarvestItem.confidence` (drafts/skill-learning confirmed=0.85, lessons=0.7), `harvest()` split по `PATTERNS_QUARANTINE_THRESHOLD=0.8`, `quarantine_items()` (схема capture_pattern, dedup vs 3 silo + vs `learned_patterns` по point_id), opt-out `PATTERNS_QUARANTINE_DISABLE=1`; баннер harvester показывает quarantined. ADR: дополнить, не заменять — принят |
| 2026-06-12 | P3.1+P3.2 DONE | `memory_maintenance.py` job `review_pending` (TTL `SKILL_PENDING_TTL_DAYS=30`, dry-run default, no-`created_at` → честный skip, ingest-события `rejected/ttl_expired`); `handle_confirm` → детач-harvest daemon-потоком (`ingest_items`, идемпотентный point_id, epoch.bump; sys.modules-регистрация до exec_module — фикс `@dataclass` краша). Live smoke: confirm → created=1 в Qdrant (тест-точка удалена) |
| 2026-06-12 | P4 тесты+observability | +15 unit ([`test_skill_learning_revival.py`](../../tests/unit/test_skill_learning_revival.py)), все PASS (после code-verify B1/B2 — 16); `record_ingest(skill_learning, rejected/skipped)` нормализуется `event_envelope` (store/action/content_hash → fact-trace тредит capture→confirm→harvest→reject). ⚠ `/mcp reconnect` для server.py+orchestrator. **Открыто: acceptance-окно 2 недели (§ P4)** |
| 2026-06-12 | P4 acceptance-наблюдение автоматизировано | [`scripts/skill_learning_acceptance.py`](../../scripts/skill_learning_acceptance.py) (5 критериев, отчёт в `data/reports/memory/`, `--final` для вердикта) + SessionStart-хук [`skill-learning-acceptance-on-start.py`](../../.claude/hooks/skill-learning-acceptance-on-start.py): прогресс-баннер раз в день (sentinel), после 2026-06-26 — финальный вердикт каждый старт, замолкает по маркеру «Acceptance вердикт» в этом §18. Opt-out `SKILL_LEARNING_ACCEPTANCE_DISABLE=1`. Baseline день 1: captures=3/10 (вкл. 2 smoke-dup имплементационного дня — лёгкий skew вверх), median_age=0d, rejects=0, arm_fired=0, dup=2. Финальную строку «Acceptance вердикт: <итог>» внести сюда после 26.06 |
| 2026-07-18 | **Acceptance вердикт: PASS** | Окно закрыто (`skill_learning_acceptance.py --final`): captures=452 (128 new + 324 dup), median_pending_age=0d, rejects=11, surfacing arm skill_learning fired 167/1131, dup=324 — все 5 критериев PASS |
