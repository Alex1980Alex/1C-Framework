# 04 — Тестирование

## Unit
- `tests/unit/test_onec_task_completion_stop.py` + `tests/unit/test_pipeline_1c_bridge.py`: **45 passed** (`-m`/`CI=1`).
- Прямое покрытие: H5 (`test_collect_config_edit`, `test_incomplete_onec_pipeline_h5`, `test_onec_pipeline_lookalike_excluded`),
  H7 (`test_advance_h7_content_guard`, обновлённый `test_advance_best_effort`).

## Smoke
- Call-graph троттл (изолированно, без spawn): missing → stale=True; fresh → False; 25000s(>6ч) → True → **CG-THROTTLE-OK**.
- `py_compile` + `ruff check` — чисто по 3 code-файлам + 2 тест-файлам.

## code-verify (Level 2, ревьюер-субагент `aa127e51ccef013c0`)
- Режим bug-fix-validation + quality-review.
- **Вердикт: PASS** `[CODE-VERIFY-PASS]`.
- Ключевое: H7-порог эмпирически подтверждён против **102 реальных артефактов** (min ANALYSIS-REPORT 3887 nonws,
  min IMPLEMENTATION-PROGRESS 2072 — запас ×10 от порога 200). H5 не вводит false-block на не-1С-сессиях
  (`config_edit` ставится только на фактическую 1С-правку). Graceful degradation полная во всех 4 путях.
- Рекомендации — необязательные (документировать эмпир. минимум; `--clear` prune manual — by-design).

## DoD
- [x] ТОП-3 (H2 · call-graph · H5) реализованы
- [x] Остаток (H7 · H6 · H1 · H3) реализован; H4 by-design (без кода)
- [x] 45/45 unit + smoke + code-verify PASS
- [x] 43.5 пробелы закрыты, ссылки на удалённые хуки исправлены
