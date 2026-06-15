# 04 — Тестирование

## Unit
- `test_lint_1c_artifacts.py`: **7 passed** (canonical/thin для analysis+impl, kind-autodetect, empty, CLI advisory).
- Широкий sweep `-k "lint or pipeline or onec or hook or import_smoke"`: **702 passed, 14 skipped**.

## Дифференциальная проверка валидатора (живые файлы)
- Тонкий 2567 (до фикса): analysis **⚠ 50**, impl **⚠ 67** — ловит отсутствие Требований/[REQ-N]/Объектов/Рисков/
  Резюме · Отклонений/МЕТАДАННЫЕ.
- Каноничные 2536/2566: **✓ 100** оба файла (без ложных флагов; после Rec1 — IMPL 2566 100, был ложный 67).
- 2567 ПОСЛЕ фикса (A): **✓ 100/100** оба — замыкание A↔C.

## Advisory-инвариант (smoke хука)
тонкий→нудж с missing-секциями; каноничный→тишина; не-артефакт→тишина; `ARTIFACT_LINT_DISABLE=1`→тишина; stub(score<30)→тишина (Rec2). Хук НИКОГДА не блокирует (exit 0).

## code-verify (субагент ade29e8e) — PASS
quality-review + behavior-preservation. Прежняя advance-логика цела; валидатор всюду advisory (exit 0/try-except/opt-out);
collision-immune. 2 рекомендации применены (Pipeline mode из scoring + гейт дребезга).

## DoD
- [x] A: 2567 перегенерированы по канону (валидатор ✓ 100)
- [x] B: SKILL усилен (чеклист секций + не-конспектируй + self-check)
- [x] C: валидатор (де-факто core-секции, advisory, lenient)
- [x] D: advisory-проводка в хук (нудж, не блок, opt-out)
- [x] 7 unit + 702 sweep + code-verify PASS; анти-deadlock соблюдён
