# Testing - roadmap_place.py

## Юнит [`tests/unit/test_roadmap_place.py`](../../tests/unit/test_roadmap_place.py) - 10 PASS
- `_date_key` (YYMMDD/none), `rank` (порядок n_matched>hits>date, 0-матчи исключены, tiebreak по дате).
- `best_sections` (heading-трекинг, уникальность, k-лимит, до-заголовка→[]).
- `suggest` все ветки: create / attach (n_matched≥2) / attach (single strong) / attach_or_create (слабая).
- live-кейс: qa_run/codepilot/getThickClientInfo → ATTACH к 260718_1C_TOOLING_AUDIT (skip-guarded).

## Верификация
- `py_compile` + ruff clean, stdlib-only.
- **code-verify** субагентом (quality-review, read-only) → **[CODE-VERIFY-PASS]**: rank/suggest/best_sections/main корректны, чистые функции тестируемы, FP «сильная связь» на шумном 1-term нет, live-кейс детерминирован (getThickClientInfo уникален для аудит-файла).
- Рек.1 (em-dash в выводе → нарушал преференцию «дефис вместо тире») **исправлена** (0 em-dash). Рек.2-5 (fence-трекинг / dedup термов / main-тест) - KISS-приемлемы, опущены.
