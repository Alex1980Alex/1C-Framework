# 03 — Кодирование

## Изменённые/новые файлы
| Файл | Что |
|---|---|
| `scripts/lint_1c_artifacts.py` (новый) | валидатор: `lint_text`/`lint_file`/`_kind_from_name`/CLI; `_ANALYSIS_SECTIONS`/`_IMPL_SECTIONS` |
| `.claude/hooks/pipeline-1c-advance.py` | `_completeness_note` (advisory, collision-immune, opt-out, score≥30 гейт) + проводка в `execute` |
| `.claude/skills/run-1c-task/SKILL.md` | шаги 2/5: «ЦЕЛИКОМ» + чеклист секций + self-check валидатором |
| 2567 `ANALYSIS-REPORT.md` / `IMPLEMENTATION-PROGRESS.md` | перегенерированы по канону (§1-§11 / полный шаблон) |
| `docs/.../43.3` | нота про advisory-валидатор в хуке |

## Тесты
`tests/unit/test_lint_1c_artifacts.py` (7): canonical→100/ok, thin→<70+missing, kind-autodetect, empty, CLI exit 0 advisory.

## reviewer-fixes (code-verify ade29e8e PASS): Rec1 — `Pipeline mode` убран из scoring-core (де-факто 68%, ложно-шумел на каноничных IMPL); Rec2 — нудж только score 30–69 (гейт дребезга на инкрементальной записи).

## Замыкание A↔C: исправленные 2567 проходят валидатор ✓ 100/100 (оба файла).
