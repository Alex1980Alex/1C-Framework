# Staged SDLC Pipeline — оркестрация с передачей артефактов (инвентаризация)

**Дата:** 2026-06-13
**Статус:** актуально
**Теги:** [pipeline, sdlc, orchestration, state-machine, artifact-handoff, slash-commands, hooks]

## Существующие в репозитории реализации staged-пайплайнов (факты)

### 1С-пайплайн (доменный, для задач 1С)
- Слэш-цепочка: `/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests`.
- Артефакты: `ANALYSIS-REPORT.md` → BSL/XML код + `IMPLEMENTATION-PROGRESS.md` → `.feature` +
  `TEST-PLAN-DETAILED.md` → JUnit XML.
- Состояние/resume: `features/<task>/.run-state.json` (chain[]: section, status, dependencies,
  created_objects, pre_check/post_check, attempts).

### OpenSpec SDD
- Жизненный цикл: propose → approve → apply → (brownfield-validate) → archive.
- Артефакты: `proposal.md`, `design.md`, `tasks.md`, `specs/<cap>/spec.md`.
- Hard-гейт: `approval-gate.py` (PreToolUse:Skill) блокирует implement/apply, если
  `.openspec.yaml` `approval.status != approved`.

### 4-step SDLC + ADR
- Шаги: Планирование → Дизайн → Кодирование → Тестирование (memory `feedback-sdd-4step-auto-adr`).
- Артефакт «План/Дизайн» = ADR (`architecture-research/adr/`, Context→Decision→Consequences→Alternatives).
- Закреплено в ADR-012..016 (roadmap 260613).

## Переиспользуемые механизмы (объективно)
| Механизм | Что даёт | Файл-образец |
|---|---|---|
| JSON state-файл + resume | состояние цепочки этапов | `.run-state.json` |
| approval-gate | hard-гейт перехода по флагу одобрения | `approval-gate.py` + `.openspec.yaml` |
| слэш-детект | определение команды из UserPromptSubmit | `shared/slash_detect.py` |
| ADR | артефакт арх-решения | `adr/NNN-*.md` |

## Внешние подходы (для справки)
- **LangGraph**: `StateGraph` с typed state + checkpointer — состояние передаётся между nodes,
  persistence между шагами (паттерн «artifact/state handoff»).
- **Spec-driven dev** (OpenSpec/Spec-Kit): артефакт-на-фазу + approval gate перед реализацией.

## Ключевые источники
- Репозиторий: `.claude/commands/`, `.claude/hooks/approval-gate.py`, `openspec/AGENTS.md`, roadmap 260613.
- LangGraph docs: `docs/documentation/Lang Chain Docs/Lang Graph/` (State, Persistence).
