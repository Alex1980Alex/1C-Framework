# ADR-041: Унификация взаимодействия SDD/OpenSpec (гл.24) ↔ 1С-пайплайн (гл.43)

**Дата:** 2026-06-25
**Статус:** proposed
**Исследование:** [cache/spec-driven-pipeline-integration-2026.md](../cache/spec-driven-pipeline-integration-2026.md)
**Связано:** ADR-012 (OpenSpec core), ADR-017/018/019 (generic+1С пайплайн), ADR-034 R3 (gate_policy)

## Контекст

Два слоя описывают одну и ту же работу над 1С-задачей разными механизмами, сшитыми через общие скиллы
(`analyze-1c-task-v2`, `implement-1c-task`). Аудит кода выявил **4 точки трения** (дублирование, не один источник правды):

1. **Два approval-гейта на `implement-1c-task`** [own, чтение кода]:
   - `approval-gate.py` (PreToolUse:Skill) → блок, если `openspec/changes/*/.openspec.yaml` `approval.status != approved`;
   - `pipeline-gate.py` (UserPromptSubmit) → `gate_1c_implement` → `.pipeline-state.json` этап 2 `approved` (G4).
   Разные события, разные сторы, **одна логика** «дизайн одобрен?». Риск: одобрено в одном сторе, не в другом →
   ложный блок ИЛИ ложный проход (нет active openspec change → approval-gate молчит, даже если pipeline не approved).
2. **Два state-стора** [own]: `.pipeline-state.json` (4 этапа) и `openspec/changes/<id>/` (`.openspec.yaml` +
   proposal/tasks/specs). Состояние одобрения дублируется → возможна дивергенция.
3. **Дублирование артефактов** [own]: `ANALYSIS-REPORT.md` (этап анализа пайплайна) и `proposal.md`/`specs/`
   (OpenSpec) описывают одно изменение; синхронизируются вручную (гл.24.9 частично: opsx:propose ест ANALYSIS-REPORT).
4. **Маршрутизация не знает про SDD** [own, grep `pipeline_1c_bridge.py` = 0 совпадений opsx/openspec]:
   `route_1c_task` решает AUTO/ask/gated по effort; решение «SDD-обёртка vs голый пайплайн» (гл.24: trivial→implement,
   medium/complex→opsx) принимается отдельно и параллельно — две несвязанные маршрутизации.

## Решение (рекомендация, downstream от spec-kit-паттерна)

GitHub-эталон **spec-kit** [WebFetch github/spec-kit]: **один** state-store на задачу (`specs/{id}/`), артефакты
**downstream**-генерация (spec→plan→tasks, анти-дрейф), **один** consistency-чекпойнт `/analyze` ПЕРЕД implement —
а не несколько конкурирующих гейтов. Применяем тот же принцип, **сохраняя оба слоя** (OpenSpec — spec-as-source +
40 MCP-tools; пайплайн — обязательные 4 этапа + 1С-методики):

- **R1 (приоритет, низкий риск — механизм уже есть).** Свести два approval-гейта в **один** через
  `shared/gate_policy.py` (ADR-034 R3, оба гейта уже логируют через него): единое решение «дизайн одобрен?»
  из **одного авторитетного источника**. Устраняет двойной блок/дивергенцию.
  **[РЕАЛИЗОВАНО 2026-06-25]** Чтение OpenSpec-approval вынесено в `shared/approval_state.py` (DRY — один
  ридер для обоих гейтов); `gate_1c_implement` (G4) теперь honors OpenSpec-approval (OR-семантика: pipeline-state
  approved ИЛИ связанный OpenSpec change `approved` → allow; JIRA-gated, non-JIRA путь не затронут);
  `approval-gate.py` переведён на общий ридер + decision-log `gate_policy`. behavior-preserving: 97 unit +
  code-verify PASS (4 инварианта). R2-R4 — proposed.
- **R2.** Единый источник одобрения: мост `.pipeline-state.json` ↔ `.openspec.yaml` — `/opsx:approve` и
  `pipeline_state approve` пишут/читают одно состояние (одно — проекция другого), а не два независимых. **[РЕАЛИЗОВАНО 2026-06-25]** `pipeline_1c_bridge.sync_approval` — односторонняя проекция OpenSpec→pipeline (idempotent, JIRA-gated, `by="openspec-bridge"`); вызывается из `gate_1c_implement` (R1-плечо). code-verify: iter1 FAIL (SystemExit от approve — BaseException, утечка) → фикс (guard `no-stage-2` + `except (Exception, SystemExit)`) → 105 unit; R3-R4 proposed.
- **R3.** Lineage вместо дублирования: `ANALYSIS-REPORT.md` → (генерация) → `proposal.md`/`specs/` как
  односторонний downstream (как spec→plan→tasks у spec-kit) + consistency-чек (аналог `/analyze`) перед
  implement — флагует дрейф ANALYSIS-REPORT ↔ proposal/specs.
- **R4.** SDD-aware маршрутизация: `route_1c_task` принимает **одно** решение, включающее SDD-vs-plain
  (trivial→голый пайплайн; medium/complex→SDD-обёртка opsx), вместо двух несвязанных правил.

## Последствия

### Положительные
- Один гейт/один источник одобрения → нет двойного блока и дивергенции (выравнивание с spec-kit «state in ONE place»).
- Lineage ANALYSIS-REPORT→proposal убирает ручную синхронизацию и дрейф.
- Одно маршрутное решение → предсказуемость (пользователь видит один выбор потока).
- Переиспользуем существующий `gate_policy` (ADR-034 R3) — минимум нового кода (simplicity-discipline).

### Отрицательные / риски
- Рефактор двух живых гейт-хуков (`approval-gate.py`, `pipeline-gate.py`) — behavior-preservation обязательна
  (дефолты == старое, регресс-тесты гейтов).
- Мост состояний (R2) добавляет связанность двух сторов; делать аддитивно + reversible.
- R3/R4 — средний объём; внедрять отдельными шагами (по одному, не разом).

## Альтернативы

- **Статус-кво (2 гейта/2 стора).** Отклонено: задокументированный риск дивергенции/двойного блока.
- **Удалить OpenSpec, оставить только пайплайн.** Отклонено: теряем spec-as-source + 40 MCP-tools + approval-модель (ADR-012 выбрал OpenSpec ядром).
- **Удалить пайплайн, оставить только OpenSpec.** Отклонено: теряем обязательные 4 этапа для trivial (ADR-018) + проводку 1С-методик через хуки (ADR-019 B′).
- **Принято:** оставить оба слоя, унифицировать гейт/состояние/lineage/маршрут (R1-R4, поэтапно, R1 первым).

## Связанные файлы
- Гейты: `.claude/hooks/approval-gate.py`, `.claude/hooks/pipeline-gate.py`, `.claude/hooks/shared/gate_policy.py`.
- Состояние: `.claude/hooks/shared/pipeline_state.py`, `openspec/changes/<id>/.openspec.yaml`.
- Маршрутизация: `.claude/hooks/shared/pipeline_1c_bridge.py` (`route_1c_task`).
- Артефакты: `ANALYSIS-REPORT.md` (analyze-1c-task-v2) ↔ `proposal.md`/`specs/` (OpenSpec).
- Доки: гл.24 (SDD), гл.43 (пайплайн), гл.43.8 (слоистость).
