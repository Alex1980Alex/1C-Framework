# 260706 — Остаточные исправления после верификации аудита 9_НАВЫКИ (260705)

> **Метод:** code-first верификация исполнения [260705_ROADMAP_SKILLS_DOCS_AUDIT.md](260705_ROADMAP_SKILLS_DOCS_AUDIT.md):
> сам прогнал все 5 заявленных тулов + 31 unit + CI-конфиг; 2 параллельных read-only агента сверили
> doc-претензии P0 (6 пунктов) и P1/P2 (6 блоков) с первоисточниками (`settings.json`,
> `skill-router.py`, `skill-router-config.json`, `code-skill-patterns.json`, `ci.yml`).
>
> **Вердикт:** реализация 260705 подтверждена — P0 6/6 FIXED (без code-drift), P1/P2 4/6 FIXED,
> 2 PARTIAL. Код-контур целиком жив: `lint_skills --strict` 0 errors/2 warnings (как заявлено),
> `gen_hooks_catalog --check` OK (99 регистраций = 19 UPS + 1 UPE + 21 Pre + 17 Post + 27 Stop + 14 SessionStart),
> 31 unit PASS, CI `skill-lint`/`skill-router-gt-lint` blocking + `skill-router-eval` advisory 0.75,
> evals.yaml-пилотов уже 13 (заявлено 3 — рост, не дефект).

---

## Найденные ошибки (остаточные) — ✅ ВСЕ ИСПРАВЛЕНЫ 2026-07-06

| # | Файл | Проблема | Статус |
|---|---|---|---|
| F1 | `.claude/skills/hooks-skills-mcp-triad/SKILL.md:24,152,166,424` | **CODE-DRIFT счётчика бандлов**: SKILL.md заявляет 53 (и в :152 — 52) vs факт `skill-router-config.json` = **66 bundles**; доменная разбивка :166 (45+7) устарела (45 grouped верно, ungrouped 7→21) | ✅ 53/52→66 во всех 4 местах; ungrouped 7→21; добавлена нота «источник истины — `domains`-ключ, регенерируемо» |
| F2 | `.../29.4_Retrieval_и_Scoring.md:18` | `experience_embeddings` подан живым («0, auto-populate ready») — дропнута 2026-06-03 (§26 Q1 ADR) | ✅ строка помечена `~~DROPPED 2026-06-03~~` (+ добавлена парная `conversation_memory`) со ссылкой на 260603_ADR_Q1 |
| F3 | `.claude/hooks/code-skill-enforcer.py:5-6` | Docstring-шапка «Event: PreToolUse \| PostToolUse» без оговорки, противоречит guard-блоку :447 | ✅ шапка переписана: «PreToolUse ONLY», явная нота о нерегистрируемом POST-mode + DO NOT re-register |
| F4 | `.claude/hooks/shared/code-skill-patterns.json:300-301` | `metadata.stats` врёт: `total_directory_rules=9`/`total_bash_rules=7` (сумма 43) vs факт 8/2 (итог 38) | ✅ 9→8, 7→2; сумма stats = 38 = факт (17+8+2+4+4+3) |
| F5 | `docs/roadmap/260705_ROADMAP_SKILLS_DOCS_AUDIT.md:23` | Сводная шапка: «97 скиллов / 52 бандла ... синхронны» — факт 98/66 | ✅ шапка исправлена (98/66) + отсылка на F1; §18 не тронут (append-only); строка :61 «19/1/21/17/27/14» уже верна |

**Верификация после правок:** JSON валиден (оба конфига), enforcer парсится, skill-lint `--strict` = 0 errors / 2 warnings (те же маргинальные BODY500), `gen_hooks_catalog --check` OK, остаточных «53/52 bundles» = 0.

## Подтверждённые pending (НЕ ошибки — честно помечены в 260705)

- **G2 live-eval** 🟡 — каркас `eval_skills.py` готов, discriminative baseline требует project-unaware
  провайдера (llm-rotation fallback'ит на claude-cli с авто-CLAUDE.md → delta=0). Ждёт инфры.
- **G4/G5 массовая разметка** — `when_to_use=0 / paths=0 / maturity unmarked=98`: конвенция+lint есть,
  адопция итеративна (unmarked = зрелый по умолчанию).
- **2 маргинальных BODY500** (framework-config 542, triad-factory 534) — осознанно не тронуты (~7% над бюджетом).

## Порядок исполнения

1. **F1** — пересчитать счётчики триады из `skill-router-config.json` (рассмотреть расширение
   `gen_hooks_catalog.py` или docs_counters на бандлы/скиллы триады — тот же класс «дрейф счётчика»,
   что уже убит для 13.2; P2.2 роадмапа 260705 закрыт лишь наполовину).
2. **F2** — 1 строка дроп-ноты в 29.4:18.
3. **F3+F4** — косметика одним коммитом (docstring + stats).
4. **F5** — сводная шапка 260705 (97→98, регистрации с UPE).
5. После — `lint_skills --strict` + `gen_hooks_catalog --check` + spot-re-verify агентом.

---

## §18 Прогресс

> Append-only, новые записи сверху.

### 2026-07-06 — P2.2 закрыт: генератор расширен на счётчики триады + self-updating guard
- `gen_hooks_catalog.py` += `router_counts()` (bundles/version/skills/домены из `skill-router-config.json` + каталог) и `verify_doc()` — сверяет заявленные в `hooks-skills-mcp-triad/SKILL.md` «N bundles»/«(N скиллов)» с фактом БЕЗ хардкода эталона (растёт каталог → правятся доки, guard ловит рассинхрон).
- CLI `--router-counts`/`--verify-doc`; `--check` принимает `bundles/skills/version`. CI: шаг `--verify-doc` в **blocking**-джобе `skill-lint` → рецидив F1-дрейфа теперь валит CI.
- Hardening по ревью (PASS): clamp `ungrouped` (домен-оверлап), graceful на недостижимый файл, ленивое `router_counts` (не ломает `--counts`/`--json`/markdown). +6 unit (11 всего), ruff+compile OK.
- Класс «дрейф счётчика бандлов» (backlog из записи ниже) закрыт тем же паттерном, что убил hook-каталог 13.2. P2.2 роадмапа 260705 закрыт полностью.

### 2026-07-06 — F1-F5 исправлены (код → доки)
- Код: F3 (docstring-шапка enforcer), F4 (metadata.stats 9/7→8/2 = 38). F1 (счётчики триады 53/52→66 ×4 места + ungrouped 7→21).
- Доки: F2 (дроп-нота 29.4 experience/conversation), F5 (шапка 260705 98/66).
- Верификация: json valid, enforcer parse OK, skill-lint 0 err/2 warn, catalog --check OK, 0 residual stale counts.
- Урок: класс «дрейф счётчика бандлов» в SKILL.md не покрыт генератором (gen_hooks_catalog покрывает только хуки 13.2). Кандидат в backlog — расширить генератор/docs_counters на bundle/skill-счётчики триады (P2.2 260705 закрыт наполовину).

### 2026-07-06 — Верификация 260705 выполнена, карта создана
- Код-контур 260705 подтверждён полностью (тулы/тесты/CI); доки P0 6/6, P1/P2 4/6 FIXED.
- 5 остаточных находок (1×P0 счётчик бандлов триады, 1×P1 дроп-нота 29.4, 3×P2 косметика).
- Статус: **pending**.
