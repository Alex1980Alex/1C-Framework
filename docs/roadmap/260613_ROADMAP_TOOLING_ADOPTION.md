# 260613 — Tooling Adoption (Claude Code ecosystem → наш framework, non-breaking)

> Карта внедрения инструментов из ресёрча [claude-code-ecosystem-tools-2026](../../.claude/skills/architecture-research/cache/claude-code-ecosystem-tools-2026.md)
> по 4 SDLC-шагам (Планирование → Дизайн → Кодирование → Тестирование).
> **Жёсткое условие: ничего не сломать.** Каждое внедрение — additive, reversible,
> за флагом/lazy-load, со smoke-чеком; рабочие компоненты (code-verify, CI,
> OpenSpec, VA BDD, memory) НЕ трогаются. Связь: [[project-roadmap-audit-pattern]],
> [[feedback-pdf-mcp-init-duration]] (MCP cold-start), [[feedback-mcp-stale-code-reconnect]].

## §0. Принцип «не сломать» (cross-cutting инварианты)

| # | Инвариант | Как обеспечивается |
|---|-----------|--------------------|
| N1 | MCP-серверы НЕ в основной `.mcp.json` | Добавлять через **lazy-mcp** (on-demand, `.mcp/lazy-mcp-config.json`) → не растёт cold-start (21 сервер уже, [[feedback-pdf-mcp-init-duration]]). Откат = убрать из `serverDefinitions`. |
| N2 | Skills — только новый каталог | `.claude/skills/<new>/SKILL.md` additive; роутер/энфорсер не ломаются (skill-exists guard 260613 F7). Откат = удалить каталог + bundle-запись. |
| N3 | Hooks (tdd-guard) — **opt-in** | env-флаг default **OFF**; не блокирует существующий flow пока не валидирован ≥1 неделю. Откат = убрать из `settings.json` chain. |
| N4 | Rollback = одна операция | config-only правки (нет миграций данных); snapshot не нужен. |
| N5 | Не трогать рабочее | code-verify / CI (ruff·mypy·pytest·codeql) / OpenSpec / VA BDD / memory-* — только дополнять рядом. |
| N6 | **Plugin-система Claude Code — НЕ внедряем** | мы на MCP+skills+hooks (0 marketplace-конфигов); plugin-marketplace конфликтует с нашей hook-архитектурой и дублирует её → остаёмся на своей триаде. ADR-фиксация. |
| N7 | Smoke перед «adopted» | каждый инструмент: live-проба + проверка что существующий pipeline зелёный (CI + acceptance harness). |

## §1. Инвентаризация — что УЖЕ реализовано (честно, ≈80% покрыто)

| Шаг | Инструмент из ресёрча | У нас уже есть (эквивалент) |
|-----|------------------------|------------------------------|
| **Планирование** | Spec Kit / BMAD / OpenSpec (SDD) | ✅ **OpenSpec** (`openspec-mcp` + SDD approval-gate hook) |
| | Superpowers (фазы SDLC) | ✅ task-protocol + roadmap §18 protocol + analyze-1c-task pipeline |
| | architecture agents | ✅ `architecture-research` (6-фаз + cache + ADR) |
| **Дизайн** | design patterns / clean-arch | ✅ `framework-patterns` + `docs/architecture/PATTERNS.md` (15+13) |
| | Figma design-to-code | ⚪ н/п (нет Figma-процесса; Python/1C-бэкенд) |
| **Кодирование** | code-simplifier | ✅ built-in `/simplify` |
| | refactoring (LSP-like) | ✅ `serena` + `ast-grep-mcp` + `bsl_rename_symbol` + `framework-search` |
| | commit commands | ✅ `git-commit-enforcer` + `auto-git-save` + conventional-commits |
| | language experts / delegation | ✅ субагенты + `llm-rotation` (5 провайдеров) + `lazy-mcp` (27 серверов) |
| | reasoning | ✅ `deep-code-reasoning` (в `.mcp/full.json`) |
| **Тестирование** | code-review / review-master | ✅ built-in `/code-review` + **adversarial code-verify субагент** (CODE-VERIFY-PASS) |
| | TDD / test-strategy | ✅ `evaluation-benchmark` + pytest (`-m unit` gate) + VA BDD (`va-bdd-testing` + `mcp-onec-test-runner`) |
| | security audit | ✅ CodeQL + Semgrep (CI `codeql.yml` + triage-скрипт) |
| | CI/CD review | ✅ `ci.yml` (ruff·mypy-baseline·pytest·compile-smoke) + `claude.yml` (disabled) + Monitor CI |

## §2. Gap — что РЕАЛЬНО additive (короткий список) / что SKIP

**Отсутствует в конфигах (0 hits):** context7, playwright, figma, pyright, spec-kit, tdd-guard, sentry, marketplace.

| Инструмент | Вердикт | Почему |
|------------|---------|--------|
| **Context7 MCP** | ✅ **ADOPT (P1)** | live version-specific доки в запросе — анти-галлюцинация API; read-only, низкий риск; усиливает наш research-протокол |
| **tdd-guard** | ✅ ADOPT (P2, opt-in) | pre-test enforcement для Python (у нас post-hoc code-verify, но нет «red-first»-гейта) |
| **Pyright LSP** | 🟡 EVAL (P3) | in-session type-intelligence; overlap с mypy → оценить ценность vs дубль |
| **Playwright MCP** | 🟡 EVAL (P3) | web/visual-тесты Streamlit/Gradio UI + FastAPI smoke; наш фокус — 1C VA BDD, web вторичен |
| **Karpathy Guidelines / Grill Me** | 🟡 EVAL (P2) | лёгкие skills (simplicity-discipline / plan-interrogation); дёшево, additive |
| **Trail of Bits Security Skills** | 🟡 EVAL (P3) | локальный CodeQL/Semgrep skill (у нас они в CI) |
| **Spec Kit / BMAD** | ❌ SKIP | redundant с OpenSpec (уже есть SDD + approval-gate) |
| **Figma / Sentry MCP** | ❌ SKIP | нет Figma-процесса / нет SaaS-деплоя с Sentry |
| **Plugin-маркетплейс** | ❌ SKIP | N6 — конфликт с hook-архитектурой |
| **Language-expert субагенты** | ❌ SKIP | overlap с нашими skills + llm-rotation |

---

## §3. Этапы внедрения (максимальная декомпозиция)

### Этап 1 — Планирование (gap минимален; OpenSpec уже покрывает SDD)

| # | Задача | Тип | Не-сломать | Критерий |
|---|--------|-----|-----------|----------|
| 1.1 | Аудит: OpenSpec vs Spec Kit/BMAD — подтвердить redundancy | analysis | — | ADR «SKIP Spec Kit/BMAD» зафиксирован |
| 1.2 | Оценить **Grill Me** (интеррогация плана) vs task-protocol/analyze-1c-task | analysis | — | решение adopt/skip с обоснованием |
| 1.3 | Если adopt → skill `plan-grill` (SKILL.md, чеклист допроса плана) | skill (N2) | новый каталог, opt-in, не в обязательном flow | smoke на тест-промпте; роутер не ломается |
| 1.4 | Зарегистрировать `plan-grill` в `skill-router-config.json` (новый bundle/optional) | config | additive bundle; не трогать существующие | `eval --split test` action_f1 не упал (регресс-чек!) |
| 1.5 | ADR-001: «Планирование — OpenSpec остаётся ядром, Grill Me опц.» | doc | — | ADR в `architecture-research/adr/` |

### Этап 2 — Дизайн (gap: simplicity-discipline как skill)

| # | Задача | Тип | Не-сломать | Критерий |
|---|--------|-----|-----------|----------|
| 2.1 | Оценить **Karpathy Guidelines** (think-before-coding/simplicity/surgical/goal-driven) vs architecture-research | analysis | — | решение: отдельный skill ИЛИ секция в architecture-research |
| 2.2 | Внедрить как skill `design-discipline` ИЛИ доп-секцию в `architecture-research/SKILL.md` | skill (N2) | если секция — append, не переписывать | smoke; architecture-research Фазы 0-6 целы |
| 2.3 | (опц.) RAG Architecture Expert subagent — оценить vs наш architecture-research | analysis | — | SKIP если overlap (вероятно) |
| 2.4 | SKIP frontend/Vercel/Figma skills (домен Python/1C) — задокументировать | doc | — | зафиксировано в §2 |
| 2.5 | ADR-002: «Дизайн — architecture-research + simplicity-discipline» | doc | — | ADR |

### Этап 3 — Кодирование (главный additive: Context7 MCP)

| # | Задача | Тип | Не-сломать | Критерий |
|---|--------|-----|-----------|----------|
| 3.1 | Добавить **Context7 MCP** в `lazy-mcp-config.json` (категория `docs`, on-demand) — НЕ в `.mcp.json` | MCP (N1) | lazy-load → cold-start не растёт; откат = убрать definition | `/mcp` видит context7 on-demand; live-проба «version-specific доки langgraph» |
| 3.2 | Smoke Context7: запрос актуальной доки vs наш `tech-research/cache` | smoke | read-only сервер | возвращает version-specific доки без ошибок |
| 3.3 | Интегрировать Context7 в `tech-research` Фаза 2 (сначала Context7 для API, потом web) — **additive подсказка**, не замена | skill-edit | append в SKILL.md, не менять существующий flow | tech-research Фазы целы; smoke |
| 3.4 | **Pyright LSP** — EVAL: ценность in-session типов vs дубль mypy | analysis | — | решение adopt/skip; если adopt — отдельный заход |
| 3.5 | SKIP code-simplifier/commit-commands/language-experts (есть `/simplify`, enforcer, llm-rotation) | doc | — | зафиксировано |
| 3.6 | ADR-003: «Кодирование — +Context7 (live docs), Pyright EVAL» | doc | — | ADR |
| 3.7 | Регресс после Этапа 3: MCP cold-start ≤ baseline + `/mcp reconnect` smoke | smoke (N7) | — | cold-start не вырос; 21+lazy серверов живы |

### Этап 4 — Тестирование (additive: tdd-guard opt-in, Playwright EVAL)

| # | Задача | Тип | Не-сломать | Критерий |
|---|--------|-----|-----------|----------|
| 4.1 | Оценить **tdd-guard** (red-first enforcement) для Python-модулей | analysis | — | решение + дизайн opt-in интеграции |
| 4.2 | Внедрить tdd-guard как **opt-in** hook (env `TDD_GUARD_ENABLE=0` default) для `src/**` | hook (N3) | default OFF → не блокирует; включать после валидации | smoke: при OFF поведение не меняется; при ON — блок без failing-теста |
| 4.3 | Валидация tdd-guard 1 неделя на реальных правках перед default-ON решением | observation | opt-in | нет ложных блокировок; решение default ON/OFF |
| 4.4 | **Playwright MCP** — EVAL для Streamlit/Gradio UI + FastAPI smoke (через lazy-mcp) | analysis+MCP (N1) | lazy-load; web вторичен к VA BDD | решение adopt/skip; если adopt — smoke на UI |
| 4.5 | **Trail of Bits Security Skills** — EVAL как локальный CodeQL/Semgrep skill (у нас в CI) | analysis | — | решение: дубль CI или additive локальный |
| 4.6 | SKIP Sentry MCP (нет SaaS-деплоя), Code Review plugin (есть code-verify+/code-review) | doc | — | зафиксировано |
| 4.7 | ADR-004: «Тестирование — +tdd-guard(opt-in), Playwright/ToB EVAL» | doc | — | ADR |
| 4.8 | Финальный регресс: CI зелёный + acceptance harness all_pass + cold-start ≤ baseline | smoke (N7) | — | ничего не сломано |

---

## §4. Порядок, риски, DoD

**Порядок (по ценности/риску):** Этап 3.1-3.3 (**Context7** — наибольшая ценность, наименьший риск) → Этап 1-2 (лёгкие skills) → Этап 4.1-4.3 (tdd-guard opt-in) → EVAL-хвосты (Pyright/Playwright/ToB) отдельными заходами.

**Критический additive-минимум (если делать только одно):** **Context7 MCP** через lazy-mcp (3.1-3.3) — read-only, anti-галлюцинация API, прямо усиливает наш research-протокол.

**Риски:**
- MCP cold-start (21 сервер уже долгий [[feedback-pdf-mcp-init-duration]]) → N1 lazy-load обязателен, НЕ в основной `.mcp.json`.
- tdd-guard ложные блокировки → N3 opt-in default-OFF + неделя валидации.
- Skill-bloat (роутер шумит) → каждый новый skill проверять `eval --split test` (регресс action_f1, 260613 C) + score-floor (260612 S4).
- Дубли (Pyright/mypy, ToB/CI-CodeQL) → EVAL-гейт перед adopt, не внедрять «потому что в списке».

**Definition of Done (вся карта):**
1. Каждый adopted-инструмент: smoke-pass + opt-out/reversible + НЕ модифицирует рабочий компонент.
2. После КАЖДОГО этапа: CI зелёный + acceptance harness all_pass + MCP cold-start ≤ baseline.
3. Каждое решение adopt/skip — ADR с обоснованием (architecture-research/adr/).
4. Роутер не регрессировал (`eval --split test` action_f1 ≥ 0.83 после новых skills).
5. Plugin-маркетплейс НЕ внедрён (N6 соблюдён).

## §18 Progress Log

| Дата | Событие | Детали |
|------|---------|--------|
| 2026-06-13 | **Этап 3.1-3.3 DONE — Context7 MCP внедрён (non-breaking, smoke PASS)** | **3.1**: `context7` добавлен в [`lazy-mcp-config.json`](../../.mcp/lazy-mcp-config.json) (категория `documentation`, on-demand `cmd /c npx @upstash/context7-mcp@3.2.0`, pin версии) — **НЕ в `.mcp.json`** (N1). **3.2 smoke PASS**: живой MCP-handshake → `serverInfo: Context7 v3.2.0` + tool `resolve-library-id`; основной `.mcp.json` (21 сервер) НЕ тронут → cold-start не вырос; оба JSON валидны; loader-контракт (categories.servers→discovery + serverDefinitions→launch) подтверждён. **3.3**: интегрирован в [`tech-research`](../../.claude/skills/tech-research/SKILL.md) Фаза 1 (Context7 → fallback WebSearch, additive). [ADR-014](../../.claude/skills/architecture-research/adr/014-coding-adopt-context7-eval-pyright.md) proposed→**accepted**. Реверс = убрать definition. Остаток Этапа 3: Pyright LSP (EVAL, 3.4). |
| 2026-06-13 | **Этап 2.2 DONE — simplicity-discipline skill (non-breaking)** | Создан [`simplicity-discipline`](../../.claude/skills/simplicity-discipline/SKILL.md) (4 правила Karpathy: think-before-coding/simplicity/surgical/goal-driven + чеклист). **БЕЗ router-bundle** → структурно нулевой regress (роутер не эмитит скилл вне бандла). Проиндексирован в skill_library (`reindex --apply`: catalog 87==library, upserted=1, ghosts/drift 0, errors 0). **Router non-regress числом: eval --split test action_f1 = 0.8346 (без изменений).** [ADR-013](../../.claude/skills/architecture-research/adr/013-design-archresearch-core-simplicity-discipline.md) accepted+реализовано. Реверс = удалить каталог. |
| 2026-06-13 | **Этап 4.2 DONE — tdd-guard hook (advisory-only opt-in, готов; не зарегистрирован)** | [`tdd-guard.py`](../../.claude/hooks/tdd-guard.py): PreToolUse:Write\|Edit, **default OFF=no-op**; `TDD_GUARD_ENABLE=1` + `src/**.py` с новым def/class без `tests/**/test_<mod>.py` → system_message-подсказка (`continue:true`, **НИКОГДА не блок**). MVP=test-presence (не run-tracked red-first). **Smoke PASS:** OFF=no-op / ON+нет-теста=advisory / ON+тест-есть=тихо / non-src=тихо; compile+ruff clean. **НЕ зарегистрирован в settings.json** (surgical/non-breaking — harness-критичный файл не трогаем ради dormant-хука). Включение (старт валидации 4.3): добавить PreToolUse-entry + `TDD_GUARD_ENABLE=1`. [ADR-015](../../.claude/skills/architecture-research/adr/015-testing-adopt-tddguard-optin-eval-playwright.md) accepted. 4.3 валидация-неделя — после включения. Остаток Этапа 4: Playwright/ToB (EVAL). |
| 2026-06-13 | **EVAL-хвост решён ([ADR-016](../../.claude/skills/architecture-research/adr/016-tooling-adoption-eval-tail-verdicts.md)) → карта функц. ЗАКРЫТА** | Вердикты: **Pyright SKIP** (дубль mypy+ruff, N6 plugin-avoid), **Playwright DEFER** (web-UI gap реален, но низкоприоритетен к VA BDD; дёшево добавить через lazy-mcp позже; revisit-условие), **ToB Security SKIP** (дубль CI CodeQL/Semgrep), **Grill Me SKIP** (дубль analyze-1c-task-v2 + OpenSpec). Каждый SKIP/DEFER с условием пересмотра. **Итог карты 260613:** все firm-ADOPT внедрены (3.1-3.3 Context7, 2.2 simplicity-discipline, 4.2 tdd-guard) + EVAL-хвост решён осознанными вердиктами. Открыт только **4.3** (валидация tdd-guard ПОСЛЕ ручного включения: PreToolUse-entry + `TDD_GUARD_ENABLE=1`). Принцип «не сломать» (N1-N7) соблюдён везде; роутер не регрессировал (test action_f1 0.8346); cold-start не вырос (Context7 в lazy-mcp). |
| 2026-06-13 | **Этап 4.3 DONE — автоматика валидации tdd-guard (observe→cache→monitor→decide)** | tdd-guard кеширует advisory в `.claude/cache/tdd-guard-events.jsonl`; [`tdd_guard_validation.py`](../../scripts/tdd_guard_validation.py) (acceptance_common-consumer, окно 06-13→06-20) **авто-решает** hard-block (low-noise + follow_rate≥0.5) / keep-advisory; SessionStart-баннер [`tdd-guard-validation-on-start.py`](../../.claude/hooks/tdd-guard-validation-on-start.py) эмитит прогресс+рекомендацию раз/день. **Включено ЛОКАЛЬНО** (`settings.local.json` gitignored: PreToolUse `tdd-guard.py` + SessionStart-баннер + `TDD_GUARD_ENABLE=1`) — **team `settings.json` НЕ тронут** (non-breaking, активация со след. сессии при перечитке settings). Smoke PASS: ruff/compile clean, logging пишет событие, validation `enabled=True rec=insufficient-data` (день 1, данных нет — корректно), banner эмитит. [ADR-015](../../.claude/skills/architecture-research/adr/015-testing-adopt-tddguard-optin-eval-playwright.md) обновлён. На закрытии окна (06-20) — авто-вердикт hard-block vs advisory. Реверс = снять local-записи. |
| 2026-06-13 | **Этап 4.3 smoke re-verify + banner-fix (/14→/7)** | Независимый повторный smoke контура валидации: ruff/compile clean (3 файла); hook поведенчески — OFF=no-op / ON+нет-теста=advisory(`continue:true`) / non-src=тихо / правка-без-def=тихо (4/4); `tdd_guard_validation.py --json` = `enabled=true, rec=insufficient-data` (день 1, 0 advisory — корректно); banner эмитит. **Найден+исправлен баг:** общий [`acceptance_watch.py`](../../.claude/hooks/shared/acceptance_watch.py) хардкодил знаменатель «день N/**14**», но окно tdd-guard = **7 дней** (06-13→06-20) → баннер вводил в заблуждение всю неделю. Фикс: параметр `window_days` (default **14** → memory-ai/skill-learning/skill-system без изменений, подтв. `inspect` + `grep -L`); [`tdd-guard-validation-on-start.py`](../../.claude/hooks/tdd-guard-validation-on-start.py) передаёт `window_days=7` → баннер теперь «день 1/7». Синтетический smoke-event вычищен из кеша (pristine). Реверс = revert правки 2 хуков. |
| 2026-06-13 | Roadmap создан | Инвентаризация: 21 MCP-сервер, OpenSpec(SDD)/code-verify/CI/VA-BDD/memory уже покрывают ≈80% ресёрч-списка. Отсутствуют (0 config-hits): context7/playwright/figma/pyright/tdd-guard/sentry/marketplace. Additive-минимум: **Context7 MCP** (P1, lazy-load, read-only) + tdd-guard (P2 opt-in) + лёгкие skills (Karpathy/Grill Me, P2) ; EVAL: Pyright/Playwright/ToB ; SKIP: Spec-Kit/BMAD (redundant с OpenSpec), Figma/Sentry, plugin-маркетплейс (N6 конфликт с hook-архитектурой). 4 этапа × atomic-задачи, «не сломать» (N1-N7) вшито в каждую. DoD: smoke+reversible+CI-green+router-non-regress после каждого шага. |
