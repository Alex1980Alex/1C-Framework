# 260705 — Глубокий аудит главы 9_НАВЫКИ (27 файлов) + сверка с GitHub-практиками

> **Метод:** 2 параллельных read-агента прочитали все 27 файлов зоны (8× 11.x, 6× 13.x, 6× 25.x, 7× 29.x)
> и сверили утверждения с кодом (`skill-router.py`, `code-skill-enforcer.py`, `settings.json`,
> `skill-router-config.json`, eval-контур 260613, `agents/learning-loop.md`). Отдельно: research
> ведущих практик skills-систем (официальный Agent Skills контракт 2026, anthropics/skills,
> superpowers, vercel-labs/skills, agentskills.io, caliper, SkillSpec, skill-framework) через
> ecosystem_scan + WebFetch — кеш [`skills-system-best-practices-2026.md`](../../.claude/skills/architecture-research/cache/skills-system-best-practices-2026.md).
> Рубрика: ОШИБКА (против кода) · УСТАРЕЛО · ФАНТОМ · СЛАБО. Паттерн волн — как в
> [аудите 5_ПАМЯТЬ 260705](260705_ROADMAP_MEMORY_DOCS_AUDIT.md) (код-first, агенты с file-ownership, адверсариальный verify).

---

## Сводная карта вердиктов

| Подглава | A (ок) | B (точечно) | C (переработка) |
|---|---|---|---|
| 9.1 СИСТЕМА_СКИЛЛОВ (11.x) | — | 11.1, 11.2, 11.4, 11.5, 11.6, 11.8 | **11.3** (роутер без A2/honest-eval), **11.7** (CI-gate неверен) |
| 9.2 ТРИАДА (13.x) | 13.6 | 13.1, 13.3, 13.4, 13.5 | **13.2** (каталог хуков устарел ~4×) |
| 9.3 LEARNING_LOOP (25.x) | 25.2 | 25.1, 25.3, 25.4, 25.5, 25.6 | — |
| 9.4 XSKILL (29.x) | — | — | **фантом, УЖЕ SUPERSEDED-баннерован 2026-07-04** — остаточно 2 аддендума |

**Интегрально:** числовые счётчики 9.1 на удивление синхронны (97 скиллов / 52 бандла / v9 / 38 правил —
правки аудита 260612 держатся), но обе главы **не знают трёх событий**: (1) **POST-контур
code-skill-enforcer (Level D/E/F) мёртв** — не зарегистрирован в settings.json, при этом описан как
живой в 5 доках; (2) **honest-eval контур 260613** (pooled action_f1 / GT-провенанс / карантин /
advisory-gate 0.75 + blocking GT-lint) и **Layer A2 + `a2_signals`** отсутствуют полностью;
(3) hook-парк вырос в ~4× (13.2: «25 хуков» vs ~99 регистраций). Реестр триады
(`hooks-skills-mcp-triad/SKILL.md`) протух сильнее самих доков (66 скиллов/v7/14 tools vs 97/v9/15).

---

## P0 — Ошибки и решение-требующие (≤ 0.5 дня)

> **✅ DONE 2026-07-05** (code-first, 3 агента с chapter-ownership + сам). **P0.1 R1 решён по коду:**
> POST-контур enforcer НЕ восстанавливать — вытеснен выделенными хуками (D→posttooluse-web-cache/
> knowledge-cache-reminder, E→code-verify-reminder ×6, F→PreToolUse phantom-guard); восстановление =
> дубли (анти-паттерн WikiDecayService). Код уже в верном состоянии, добавлен guard-комментарий
> «DO NOT re-register» + smoke PRE-путь exit 0. Доки (11.1/11.2/11.4/13.2/13.3) помечают D/E/F
> superseded. P0.2 (.mcp.json не settings.json + D:\→C:/), P0.3 (события 3 хуков по settings.json —
> factory-enforcer/task-protocol-observer=PreToolUse, auto-git-save=Stop), P0.4 (CREATE внутри
> субагента, не host — 25.3/25.6), P0.5 (8 доменов из skill-router-config — 11.5/11.6), P0.6 (38 правил
> не 43) — исправлены, агенты сверяли с settings.json/config напрямую. Link-sweep 72 ссылки PASS.
> **Бонус §БП G1 (R3) в этой же волне:** `scripts/lint_skills.py` (9 правил бюджетов 2026) + advisory
> CI-job; первый прогон 49 errors/5 warns по 97 скиллам (массовый DEADLINK от перенумерации глав —
> подтвердил `project_docs_renumbering_broke_enforcement`). Discrimination-тест PASS.

| # | Файл(ы) | Проблема | Действие |
|---|---|---|---|
| P0.1 | 11.1:44-45,68 · 11.2:257-267 · 11.4:206-267 · 13.2:121-122 · 13.3:163-165 | **POST-контур `code-skill-enforcer` (Level D/E/F: cache-reminder, post-verification, LEARN backup) мёртв** — в settings.json одна регистрация PreToolUse `Write\|Edit\|Bash` (:270); POST-mode в коде есть (`code-skill-enforcer.py:445-459`), но не выполняется НИКОГДА. 5 доков описывают как живой | **R1 (выбор пользователя, аналог kb-lint 260705):** (a) вернуть PostToolUse-регистрацию ИЛИ (b) пометить D/E/F «не зарегистрированы» в 5 доках. Код-first → рекомендация (a), если контур ценен |
| P0.2 | 13.4:114-131 | «MCP-серверы регистрируются в `.claude/settings.json → mcpServers`» — ключа там НЕТ; факт — `.mcp.json` в корне (+ профили `.mcp/*.json`) | Исправить на `.mcp.json`; заодно пути `D:\` → `C:/` (13.2:167, 13.4:122-128) |
| P0.3 | 13.2:125,127 · 11.2:83,259-263 | События хуков перепутаны: `factory-enforcer` = PreToolUse (не PostToolUse:Write); `auto-git-save` = Stop (на PostToolUse — другой файл `posttooluse-auto-git-save`); `task-protocol-observer` = PreToolUse (не PostToolUse) | Исправить по settings.json |
| P0.4 | 25.3:3 · 25.6:14 | «CREATE-фаза выполняется главным Claude (host) после возврата субагента (race conditions)» — **противоречит коду и соседней главе**: `agents/learning-loop.md:111-140` CREATE внутри субагента (Write SKILL.md + регистрация в конфиг); живой A3-прогон тоже | Убрать host-CREATE тезис из 25.3 + race-строку из 25.6 |
| P0.5 | 11.6:61 · 11.5:209 | Состав «8 доменов» неверен (перечислены tech/testing/devops/workflow — из `code-skill-patterns.json`); факт config: `1c, framework, claude-code, langchain, research, memory, llm, tools` (в 11.3:180-197 — правильно; противоречие внутри главы). 11.5: «6 доменов» | Исправить состав; 11.5 → 8 |
| P0.6 | 13.2:152 | «43 правила» `code-skill-patterns.json` — факт **38** (11.4:392 верно) | 38 |

## P1 — Устаревшее (1 день)

> **✅ DONE 2026-07-05/06** (code-first, 3 агента chapter-ownership + сам). **Код (P2.1):**
> `scripts/gen_hooks_catalog.py` (+5 unit) — генератор каталога хуков из settings.json (single
> source), убивает класс «4×-дрейф»; live 99 регистраций (19/1/21/17/27/14) = аудит, `--check`
> детектит drift обе стороны. **Доки:** 11.3 (слои A/A2/B/C/D + intent-модификатор + honest-eval
> 260613: pooled action_f1, GT 95/64-31 split, TF-IDF artifact-имена), 11.7 (CI blocking
> `skill-router-gt-lint` + advisory `skill-router-eval` 0.75 action_f1 [0.7708]; живые контуры
> мониторинга), 11.8 (Phase 15 перекрыт, metadata.stats-нота), 13.2 (каталог регенерирован
> генератором — `<!-- АВТО-ГЕНЕРАЦИЯ -->` блок, `--check` OK), реестр триады (97/v9/52/15/99),
> 25.x (research-task-detector не зарегистрирован / A3-прогон duckdb-analytics / VERIFY-таблица
> subagent-vs-host), 29.1/29.4 (дропнутые коллекции + ссылка на 11.3). Link-sweep 87 ссылок PASS,
> 13.2-числа = генератор. P2.1 (генератор) закрыт этой волной.

- **11.3 (C):** нет Layer **A2** (1С-сигналы + literal skill-name `\b`, `skill-router.py:276,375-383`; конфиг-веса `a2_signals` — вынос 260613 B1); «Layer D = Intent Classification» — факт: D = **semantic fallback** (:429), intent — модификатор порога (:309-315,592-601); нет honest-eval 260613 (pooled action_f1, GT 95 строк 64/31 train/test, карантин 22, CI blocking GT-lint + advisory eval 0.75, факт 0.7708); имена TF-IDF артефактов: `idf_weights.npy`/`centroids_normalized.npy`/`metadata.json` (не `idf.npy`/`centroids.json`).
- **11.7 (C):** CI-gate описан как blocking macro-F1≥0.70 — факт: blocking = `skill-router-gt-lint` (schema+no-leakage), eval = **advisory** `continue-on-error` 0.75 pooled action_f1; не отражены живые контуры: `skill-usage-metrics`+`posttooluse-skill-metrics`, `skill-quality-monitor`, `tool-effectiveness.jsonl`+`tool_usage_report.py`, acceptance-харнесс + SessionStart-баннер, Qdrant `skill_library`.
- **13.2 (C):** каталог хуков 25 → ~99 регистраций (UPS 19/Pre 21/Post 17/Stop 27/SessionStart 14); SessionStart описан одним хуком — их 14. **Решение P2.1 — генератор** (см. ниже).
- **Реестр триады** `hooks-skills-mcp-triad/SKILL.md`: 66 скиллов→97, v7→v9, 14 tools→15 (docs_counters это уже флагал — теперь причина ясна).
- **25.4:** `research-task-detector.py` существует, но НЕ зарегистрирован (13.2 честно помечает ⚠, 13.5/13.6 опираются как на живой) — пометить всюду.
- **25.1/25.5:** живой прогон A3 2026-06-13 (skill `duckdb-analytics`, 45-й bundle) не упомянут; единственный пример — гипотетический Redis.
- **25.1/25.2/25.3 VERIFY-дрейф:** субагент = inline-verify (no sub-subagents, max 2 retries) vs host-скилл = ревьюер-субагент (Ralph max 3) — оба верны, нужна таблица «где какой VERIFY».
- **29.1/29.4 аддендумы (глава уже SUPERSEDED):** (a) update-блоки 2026-04-30 подают `experience_embeddings`/`conversation_memory` живыми — дропнуты 2026-06-03 (ADR Q1), 1 строка; (b) 29.4 описывает ЖИВОЙ skill-router с неверными слоями/формулой — заменить ссылкой на 11.3.
- **11.8:** Phase 15 `learn-from-logs.py` не существует (план перекрыт honest-eval 260613 + `tune_skill_router.py`); «обновить metadata.stats» противоречит 11.4:394 (stats устарел).

## P2 — Структура

- **P2.1 Генератор каталога хуков:** 13.2 регенерировать скриптом из `settings.json` (single source; таблица события×хук авто-выводом) — устраняет класс «4× дрейф» навсегда. Код: `scripts/gen_hooks_catalog.py` (или секция в docs_counters).
- **P2.2 Реестр триады:** синхронизировать `hooks-skills-mcp-triad/SKILL.md` счётчики (или тоже генератором).
- **P2.3 11.3+11.7 переработка** по коду (после P1-фактов).

---

## §БП — Сверка с лидерами (Agent Skills 2026 / superpowers / caliper / SkillSpec / skill-framework)

### Где мы УЖЕ соответствуем
| Практика лидера | У нас | |
|---|---|---|
| Router-level honest eval (GT, split, CI) | eval-skill-router 260613: pooled action_f1, провенанс, GT-lint blocking | ✅ сильнее большинства |
| Enforcement до записи (hooks) | code-skill-enforcer PreToolUse + phantom-guard | ✅ |
| Авто-создание скиллов (Voyager-style) | learning-loop 5 фаз + verify-гейт + live A3 | ✅ |
| Карантин знаний | skill-learning pending/confirm + TTL-30d | ✅ |
| Semantic discovery | Layer D + Qdrant skill_library | ✅ |

### Разрывы (кандидаты в улучшения)

| # | Разрыв | Практика лидера | У нас | Оценка |
|---|---|---|---|---|
| G1 | **Skill-lint в CI** | skill-framework 17 правил; официальные бюджеты: body <500 строк, `name`≤64, `description`≤1024, третье лицо, **листинг усекает when_to_use+description до 1536 симв.**; dead links; SkillSpec: 46% скиллов — name-коллизии | docs_counters ловит только счётчики-дрейф; бюджеты/усечение/dead-links/коллизии НЕ линтятся (docs_counters уже показал `learning-loop > 500 строк`) | Сложность **Low**, ценность **High** — quick win: `scripts/lint_skills.py` + CI advisory |
| G2 | **Per-skill evals + baseline** | evals/evals.json В директории скилла; обязательный baseline «без скилла»; дельта pass_rate/tokens; caliper pass@k + класс «cheat» | Только router-level eval (активация); польза СОДЕРЖИМОГО скилла не меряется никогда | Сложность Mid-High, ценность High — начать с 3-5 критичных скиллов (bsl-development, memory-unified, code-verify) |
| G3 | **Description tuning** | Генерация should/not-should-trigger промптов + hit rate — оптимизация描аний как артефакт | GT-based eval есть, но описания скиллов не тюнятся систематически | Сложность Mid, ценность Mid — после G1 (лint выявит кандидатов) |
| G4 | **Frontmatter 2026** | `when_to_use`, `paths` (glob-активация!), `hooks` в скилле, `context: fork`, `disallowed-tools`, `arguments` | Наши SKILL.md — name+description; `paths`-активация могла бы заменить часть enforcer-паттернов | Сложность Low-Mid, ценность Mid — инвентаризация полей + пилот `paths` |
| G5 | **Зрелость каталога** | `.curated`/`.experimental` конвенция (vercel-labs), version-pinning | 97 скиллов без градации зрелости | Сложность Low, ценность Low-Mid |
| G6 | **Plateau → удалять** | Anthropic: при плато КОРОТИТЬ скилл (over-constrained); reasoning-why > ALWAYS/NEVER | Скиллы только растут (learning-loop 500+ строк) | Принцип → в 11.5 + skill-lint warning |

**Рекомендация:** G1 (код, quick win) → P0/P1 docs-волны → G2 пилот (3 скилла) → G4 инвентаризация. G3/G5 — backlog.

---

## Рекомендации (порядок исполнения)

1. **R1 (решение пользователя):** судьба POST-контура code-skill-enforcer (P0.1) — вернуть регистрацию или задокументировать отключение.
2. **R2:** волна P0 (6 пунктов) — ошибки/противоречия, один проход агентами с file-ownership.
3. **R3 (код):** §БП G1 — `scripts/lint_skills.py` (бюджеты 500/64/1024/1536, dead links, name-collisions, third-person эвристика) + CI advisory job + прогон по 97 скиллам → починка топ-нарушителей.
4. **R4:** волна P1 (11.3/11.7 переработка + 13.2-генератор P2.1 + реестр триады P2.2 + 25.x точечно + 29.x аддендумы).
5. **R5 (код):** §БП G2 пилот — evals для 3 скиллов с baseline.
6. После волн — `scripts/docs_counters.py --check` + re-verify агентом.

> ⚠ Roadmap-оценки исторически завышены 1.5–3×; инвентарь тут точный (27/27 файлов, 3 агента).

---

## §18 Прогресс

> Append-only, новые записи сверху.

### 2026-07-05 — P0 исполнен (code-first) + §БП G1 skill-lint
- P0.1 R1 решён по коду: POST-контур enforcer superseded (не восстанавливать — дубли), guard-комментарий + 5 доков помечены. P0.2-P0.6 (MCP-регистрация/события хуков/CREATE-в-субагенте/8 доменов/38 правил) исправлены 3 агентами (сверка с settings.json/config). Link-sweep 72 ссылки PASS.
- §БП G1: `scripts/lint_skills.py` + advisory CI-job (`skill-lint`, continue-on-error). Первый прогон: 49 errors/5 warns / 97 скиллов — массовый DEADLINK (перенумерация глав), `1c-debug-hmr` DESC1024, BODY500 у va-bdd/implement-1c/hooks-triad. Discrimination-тест PASS.
- Осталось: P1 (11.3/11.7 переработка + 13.2-генератор + реестр триады + 25.x/29.x аддендумы), P2 (генераторы), §БП G2 (per-skill evals) / G3-G6. Отдельная зачистка 49 skill-lint errors (перенумерация — [[project_docs_renumbering_broke_enforcement]]).

### 2026-07-05 — Аудит выполнен, дорожная карта создана
- 3 параллельных агента: аудит 9.1+9.2 (14 находок ranked, счётчики-таблица), аудит 9.3+9.4 (7 находок; 9.4 = фантом, уже SUPERSEDED-баннерован), research (кеш `skills-system-best-practices-2026.md`, 10 фактов + 8 отличий лидеров).
- Главные находки: мёртвый POST-контур enforcer (5 доков врут), honest-eval 260613 не задокументирован, 13.2 отстаёт в 4×, «CREATE в host» противоречит коду, 29.x аддендумы про дропнутые коллекции.
- Статус: **pending**; R1 требует решения пользователя; R3 (skill-lint) — готовый к исполнению код-quick-win.
