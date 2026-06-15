# 02 — Дизайн реализации

## H5 межсессионный gate (реальный баг)
- **Корень:** детект 1С-задачи = только `pipeline.updated_at >= session_start`. Задача в 2 сессии: S2 не видит.
- **Решение:** двойной детект — `_onec_pipeline_updated` (обновлён в сессии) **ИЛИ** `_incomplete_onec_pipeline`
  (этапы не-done) **ПРИ** `config_edit` (1С-правка `/configuration/`|`.bsl/.mdo/.os` в этой сессии).
- **Анти-false-block:** при `slug=None` без `config_edit` → exit 0 (стрей-незавершённый пайплайн без 1С-работы не блокирует).
- **Отклонено:** «всегда блокировать при любом incomplete-пайплайне» → false-block на не-1С-сессиях.

## H2 сводка петель
- `_write_loops_report(slug, sig)` → `pipeline/<slug>/LOOPS.md`, переиспользует `_collect_signals`. best-effort.
- Поверхность для H1 (указатель на rollup) + H3 (строка «W per-task: НЕ запущен»).

## Call-graph на commit
- `build_call_graph.py` без `--paths` (full re-parse, дорого) → **троттл ≤1/6ч** через spawn-sentinel.
- Sentinel touched ДО spawn (анти-thundering-herd на серии коммитов). Detached, внутри try/except (не блок git).
- `graph_embeddings` (Qdrant) — manual (тяжёлый embed-pass), осознанно вне scope.
- **Отклонено:** rebuild на каждом коммите (минуты × каждый commit) и per-project отдельные DB (граф-запросы ждут shared DB).

## H7 false-advance guard
- `_artifact_has_content` ≥200 непробельных символов. Эмпирика: реальные отчёты ≥2000 → запас ×10, нет false-block.
- Инкрементальная запись: header-only не продвинет, заполняющий Edit — продвинет.

## H6 preflight ТЗ
- `run-1c-task` SKILL, этап 2.4: self-check полноты ТЗ перед авто-approve → иначе СТОП+вопрос. Конкретизация «AUTO ≠ игнор блокеров».

## H1/H3/H4 — docs/by-design
- H1: `tool-effectiveness.jsonl` = **отчётный** (потребитель `--rollup`), не обучающий контур. Правка 43.3.
- H4: apply_pattern неизмерим — by-design, без кода.

## Approved: human (ретроспективно — реализация уже verify-PASS)
