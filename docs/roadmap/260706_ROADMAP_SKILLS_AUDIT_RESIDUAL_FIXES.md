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

## Найденные ошибки (остаточные)

| # | Файл | Проблема | Приоритет |
|---|---|---|---|
| F1 | `.claude/skills/hooks-skills-mcp-triad/SKILL.md:24,152,166,424` | **CODE-DRIFT счётчика бандлов**: SKILL.md заявляет 53 (и в :152 — 52, внутренняя несогласованность) vs факт `skill-router-config.json` = **66 bundles**; доменная разбивка :166 (45+7) устарела. Скиллы 98 ✓ / v9 ✓ / 15 tools ✓ | P0 (реестр триады — справочный вход) |
| F2 | `docs/framework documentation/9_НАВЫКИ/…/29.4_Retrieval_и_Scoring.md:18` | `experience_embeddings` в таблице подан как живой («0, auto-populate ready») — коллекция дропнута 2026-06-03 (§26 Q1 ADR); дроп-нота есть в 29.1:120, в 29.4 отсутствует (помечен только `visual_grounding`) | P1 (глава SUPERSEDED-баннерована, но таблица вводит в заблуждение) |
| F3 | `.claude/hooks/code-skill-enforcer.py:5-6` | Docstring-шапка декларирует «Event: PreToolUse \| PostToolUse» без оговорки — guard-блок «DO NOT re-register» живёт ниже (:447-458), шапка противоречит ему при беглом чтении | P2 (косметика) |
| F4 | `.claude/hooks/shared/code-skill-patterns.json:298-305` | Внутренний `metadata.stats` врёт (9 directory / 7 bash, сумма 42 vs факт 38); 11.4:394 честно флагает stats как устаревший, но сам json не чинён — синхронизировать или удалить блок stats | P2 (доки на него не опираются) |
| F5 | `docs/roadmap/260705_ROADMAP_SKILLS_DOCS_AUDIT.md` (шапка/P1) | Сам роадмап несёт устаревшие цифры: «97 скиллов» (факт 98), разбивка регистраций «19/21/17/27/14 = 98» при итоге 99 (опущен UserPromptExpansion=1, `slash-command-tracker.py`) | P2 (исторический документ; поправить только сводную шапку, §18 append-only) |

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

### 2026-07-06 — Верификация 260705 выполнена, карта создана
- Код-контур 260705 подтверждён полностью (тулы/тесты/CI); доки P0 6/6, P1/P2 4/6 FIXED.
- 5 остаточных находок (1×P0 счётчик бандлов триады, 1×P1 дроп-нота 29.4, 3×P2 косметика).
- Статус: **pending**.
