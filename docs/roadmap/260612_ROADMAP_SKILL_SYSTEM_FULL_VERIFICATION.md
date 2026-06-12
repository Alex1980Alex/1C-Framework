# 260612 — Skill System Full Verification (жизненный цикл скиллов + стык с Unified Memory)

> Четвёртый блок семейства full-verification (после memory-ai / pdf-docs /
> LinkRegistry). Объект: СИСТЕМА_СКИЛЛОВ ([глава 11](../framework%20documentation/11_СИСТЕМА_СКИЛЛОВ/11.1_Обзор.md))
> как полный жизненный цикл — создание → регистрация → маршрутизация →
> enforcement → активация → измерение → обучение — и её **стык с Unified Memory**
> (колонки `skill_library`, skill-learning, surfacing-плечи карты
> [27.12](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md)).
> Research-база: кеш [skill-library-lifecycle-testing-2026](../../.claude/skills/architecture-research/cache/skill-library-lifecycle-testing-2026.md)
> (Voyager: в библиотеку — только верифицированное; review свежим субагентом;
> lifecycle/provenance/rollback как требование).

## 1. Инвентаризация (фактическое состояние 2026-06-12, live-снятие)

**Каталог:** 87 каталогов скиллов в `.claude/skills/` (включая `_archived`).
Router: `skill-router-config.json` (16 bundles, 3-layer v9). Enforcement: 6 уровней
A-F (глава 11.4), конфиг Level A — `shared/code-skill-patterns.json` (на месте).

**Жизненный цикл — стадии-«писатели» (вход):**
| # | Стадия | Механизм | Состояние |
|---|--------|----------|-----------|
| C1 | Ручное создание | `doc-to-skill`, 11.5 формат | живой |
| C2 | Авто-создание из опыта | learning-loop (глава 25, 5 фаз) | живой код; **частота производства не измерена** |
| C3 | Индексация в память | `skill_library` Qdrant (80 точек, indexed_at 04-30..06-12) | живой, но **drift** (см. S1/S2) |
| C4 | Карантин уроков | skill-learning pending/confirm (260611 revival) | живой, acceptance-окно идёт |
| C5 | Харвест | `skills-harvester.py` (Stop) | живой, но **вне ingestion-лога** (S3) |

**Стадии-«читатели» (выход):**
| # | Стадия | Механизм | Состояние |
|---|--------|----------|-----------|
| U1 | Маршрутизация | `[SKILL-ROUTER]` баннер (keyword+fuzzy+TF-IDF) | живой |
| U2 | Enforcement | task-protocol-enforcer (Write/Edit block до `Skill()`), code-skill-enforcer, skill-eval-enforcer | живой (блокировки наблюдаются ежесессионно) |
| U3 | Активация | `Skill()` tool → контент в контекст | живой |
| U4 | Memory-surfacing | `memory-first-hook` плечо skill_library в `[MEMORY CONTEXT]` | живой, но **шумный** (S4) |
| U5 | Метрики | `skill-usage-metrics.py` → `data/skill-accuracy.jsonl`, `posttooluse-skill-metrics`, `skill-quality-monitor` | код жив; **петля не замкнута** (S6) |
| U6 | CI-гейт качества | `skill-router-eval` (F1≥0.75) | job SUCCESS, но **вердикт не подтверждён** (S5) |

## 2. Проблема (что нашла инвентаризация)

- **S1 — призрак в библиотеке**: точка `1c-mcp-toolkit` живёт в `skill_library`,
  хотя скилл deprecated и каталог удалён — **подтверждено живьём**: всплывал в
  `[MEMORY CONTEXT]` этой сессии как рекомендация. Память рекомендует мёртвый
  инструмент. Нет prune-механизма при удалении/архивации скилла.
- **S2 — drift каталог↔библиотека**: 7 реальных скиллов не проиндексированы
  (`1c-debug-hmr`, `1c-mcp-crud`, `framework-patterns`, `post-indexing-analysis`,
  `sandbox-execution`, `1c-config-knowledge`, `obsidian-vault`) — surfacing их
  не видит; реиндекс-каденса нет (аналог D5 pdf-docs).
- **S3 — индексация вне write-contract §26**: payload `skill_library` без
  `content_hash`, 0 событий `skill_library` в `memory-ingestion.log` — поток
  невидим для `cross_store_sync`/fact-trace/observability (контракт 260609 P1.3
  покрыл learned_patterns, но не skill_library).
- **S4 — surfacing-шум**: плечо skill_library заполняет топ `[MEMORY CONTEXT]`
  скиллами со скорами 0.005-0.006 (наблюдение всей текущей сессии) — почти
  нерелевантные подсказки занимают слоты вместо реальных паттернов; gating
  по абсолютному скору отсутствует или не работает для этого плеча.
- **S5 — качество роутера не доказано**: CI job `skill-router-eval` SUCCESS, но
  внутри возможен silent-skip («ground-truth not in repo» — при этом файл
  tracked И gitignored одновременно); F1≥0.75 как гейт не подтверждён живым
  вердиктом; ground-truth не пополняется.
- **S6 — петля метрик разомкнута**: `skill-accuracy.jsonl`/`skill-quality-monitor`
  пишут, но никто не читает → нет деградационного сигнала «скилл устарел/мешает»
  (ср. Voyager: в библиотеке живёт только верифицированное; survey: lifecycle +
  provenance + rollback обязательны).
- **S7 — верификация при создании не систематична**: C1/C2 не имеют
  гейта «скилл работает» перед регистрацией (Voyager-критерий self-verification;
  доступен паттерн review свежим субагентом). Phantom-блокировки
  code-skill-enforcer при несуществующем skill — известный класс (CLAUDE.md).
- **Тестовое покрытие**: e2e цепочек жизненного цикла нет; unit покрытие router
  есть частично; 27.12 не показывает skill-систему как ВХОД в память (стык
  документирован фрагментарно).

Целевая модель: **каждая стадия цикла исполняема и измерима; библиотека в памяти
= зеркало живого каталога (без призраков и пропусков, под write-contract);
surfacing-плечо скиллов даёт сигнал, а не шум; качество роутера доказано числом;
деградация скилла видна и ведёт к review/архиву.**

## 3. Тест-карта цепочек вход→выход

### Блок A — входы (создание → регистрация → индексация)
| # | Цепочка | Шаги | Критерий приёмки |
|---|---------|------|------------------|
| A1 | C1 create→index | новый тест-скилл → reindex → точка в `skill_library` с `content_hash` + `record_ingest` | drift-нуль на тест-скилле; событие в ingestion-логе |
| A2 | C1-delete→prune | удаление/архивация скилла → prune точки | призраков нет (S1-регресс) |
| A3 | C2 learning-loop | learning-loop производит скилл → верификация (code-verify) → регистрация | путь исполнен живьём ≥1 раз, verify-гейт обязателен |
| A4 | C4 quarantine | capture→confirm→harvest (уже под acceptance 260611) | сослаться, не дублировать |
| A5 | sync-каденс | reindex skill_library в maintenance | drift каталог↔библиотека = 0 после каденса |

### Блок B — выходы (роутинг → enforcement → активация → измерение)
| # | Цепочка | Шаги | Критерий |
|---|---------|------|----------|
| B1 | U1 router golden | прогон `eval-skill-router` с реальным вердиктом | F1≥0.75 ЧИСЛОМ в §18; ground-truth пополнен ≥20 свежими кейсами |
| B2 | U2 enforcement | негативный прогон: Write без Skill() → блок; phantom-skill в patterns → честная ошибка конфига, не блок | оба честные |
| B3 | U4 surfacing-сигнал | промпт с явной skill-темой vs нерелевантный | релевантный скилл в топе с заметным скором; нерелевантные отсечены порогом (S4-фикс) |
| B4 | U5 метрики→решение | накопленный `skill-accuracy.jsonl` → отчёт «кандидаты на review/архив» | потребитель существует, отчёт генерится |
| B5 | стык 27.12 | карта показывает skill-библиотеку как колонку/поток | doc == реальность |

### Блок C — отказы (honest-failure)
| # | Цепочка | Критерий |
|---|---------|----------|
| C1 | Qdrant down при surfacing | плечо умирает честно (trace), баннер без скиллов, сессия живёт |
| C2 | Skill() несуществующего имени | честная ошибка, без фантомного контента |
| C3 | router-eval без ground-truth | job ЯВНО помечен skipped (не SUCCESS-маскировка) |

## 4. Фазы

### P0 — Гигиена библиотеки (фундамент)
| # | Задача | Критерий |
|---|--------|----------|
| P0.1 | **S1/S2**: reindex-скрипт skill_library (mirror каталога: upsert живых, prune удалённых/архивных; детерминированный point_id от skill_name) + прогон | 87-каталог == библиотека (минус `_archived`); призрак `1c-mcp-toolkit` удалён |
| P0.2 | **S3**: индексатор под write-contract §26 (`content_hash` + `record_ingest`) | события в ingestion-логе, fact-trace тредит скилл |
| P0.3 | Baseline-числа в §18 (точки, drift, последний indexed_at, surfacing-доля скиллов в баннерах) | зафиксировано |

### P1 — ВХОД: A1-A3, A5
- A1/A2 живыми прогонами + регресс-тест prune.
- A5: job `reindex_skill_library` в maintenance-каденсе (паттерн `reindex_wiki`).
- A3: один полный learning-loop прогон с verify-гейтом; зафиксировать выход.

### P2 — ВЫХОД: B1-B4 + S4-фикс
| # | Задача | Критерий |
|---|--------|----------|
| P2.1 | **S5**: вскрыть фактический вердикт CI router-eval; ground-truth: статус в git нормализовать (tracked XOR ignored), пополнить ≥20 кейсов из живых сессий; первый честный F1 в §18 | B1 PASS |
| P2.2 | **S4**: порог/вес для плеча skill_library в memory-first-hook (абсолютный score-floor или доля слотов) — скиллы не вытесняют паттерны при микро-скорах | B3 PASS; доля шумовых skill-слотов в баннере ↓ (замер до/после) |
| P2.3 | **S6**: потребитель метрик — отчёт «skill review candidates» (low-usage + low-accuracy + stale) в maintenance-дашборд | B4 PASS |
| P2.4 | B2/C2/C3 негативные прогоны | честность зафиксирована |

### P3 — Стык с Unified Memory (карта и наблюдаемость)
- 27.12: skill-вход в карту (skills-harvester/индексатор как писатель, плечо
  surfacing как читатель) — сейчас стык размазан по 11.x/27.x.
- fact-trace: жизнь скилла (index→surface→activate→metric) тредится по ключу.

### P4 — Acceptance (2 недели, 5-й потребитель `acceptance_common`)
0 призраков и 0 drift после каденса; ingestion-события skill_library живые;
F1 числом ≥0.75; surfacing-доля шума ниже зафиксированного порога; отчёт
review-кандидатов генерится в каденсе; C1-C3 честные.

## 5. Порядок и оценка

P0 (0.5d) → P1 (0.5-1d) → P2 (1-1.5d: S5 может вскрыть, что eval никогда не
работал — тогда +ground-truth работа) → P3 (0.5d) → P4 (0.5d + 2 недели).
[[project-roadmap-audit-pattern]]: перед P2 повторно снять surfacing-долю — S4
мог измениться смежными правками кеша (§24).

## 6. Риски

- **Prune необратим** — перед удалением точек snapshot коллекции (методика
  [[reference-qdrant-collection-aliases]]); призрак подтвердить отсутствием каталога.
- **S4-порог** режет и полезные подсказки — калибровать на живых сессиях
  (до/после замер), knob через env, откат = убрать порог.
- **Ground-truth дорого** — пополнять из реальных транскриптов (router-баннер +
  фактически активированный скилл = готовая разметка), не выдумывать.
- **Reindex-каденс** не должен дублировать точки — детерминированный point_id
  обязателен (паттерн `content_hash.point_id`).

## §18 Progress Log

| Дата | Событие | Детали |
|------|---------|--------|
| 2026-06-12 | Roadmap создан | Live-инвентаризация: 87 каталогов / 80 точек skill_library (drift 7 + призрак `1c-mcp-toolkit`, всплывавший в surfacing этой сессии); индексация вне write-contract §26 (0 событий в ingestion-логе); surfacing-плечо шумит микро-скорами 0.005-0.006; CI router-eval SUCCESS без подтверждённого вердикта (ground-truth tracked+gitignored одновременно); петля метрик `skill-accuracy.jsonl` без потребителя. Findings S1-S7, тест-карта A1-A5/B1-B5/C1-C3, фазы P0-P4. Research: Voyager (verified-only library, self-verification до регистрации), Claude Code skills экосистема (review свежим субагентом, lifecycle/provenance/rollback) — кеш skill-library-lifecycle-testing-2026 |
