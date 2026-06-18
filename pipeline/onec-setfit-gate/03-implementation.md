# 03 — Кодирование

## Новые файлы
- [`.claude/hooks/shared/onec_setfit_gate.py`](../../.claude/hooks/shared/onec_setfit_gate.py) — гейт слоя ②:
  `setfit_prob`, `is_enabled`, `model_dir`, `threshold`, `_load_model` (lazy, кэш на процесс),
  `_positive_prob`, `status`, CLI `info`/`predict`.
- [`scripts/train_onec_setfit.py`](../../scripts/train_onec_setfit.py) — обучение: `load_rows`
  (drop quarantine), `partition` (split-поле/sha1%5), `to_examples` (label=int(is_1c), e5-префикс),
  `summarize`/`dry_run`, `train` (lazy setfit/datasets, save + test P/R/F1). `--model`, `--dry-run`.
- [`.claude/skills/architecture-research/adr/025-…md`](../../.claude/skills/architecture-research/adr/025-1c-detector-setfit-stage2a-scaffold.md) + запись в `adr/_index.json`.
- [`tests/unit/test_onec_setfit_gate.py`](../../tests/unit/test_onec_setfit_gate.py) — 16 тестов.

## Правки
- [`pipeline_1c_bridge.py`](../../.claude/hooks/shared/pipeline_1c_bridge.py): `_setfit_prob_safe`,
  `_semantic_signal`, `_SETFIT_THRESHOLD`; `route_1c_task` зовёт `_semantic_signal`, добавлен `semantic_source`.
- [`scripts/eval_1c_detector.py`](../../scripts/eval_1c_detector.py): флаг `--setfit` (ставит `ONEC_SETFIT_ENABLE=1`).
- [`43.5_СКВОЗНАЯ_КАРТА.md`](../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.5_СКВОЗНАЯ_КАРТА.md): диаграмма слоя ②.
