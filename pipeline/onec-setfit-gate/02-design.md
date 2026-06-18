# 02 — Дизайн реализации

**Статус:** одобрен (пользователь подтвердил дизайн в чате 2026-06-18). Детали — [ADR-025](../../.claude/skills/architecture-research/adr/025-1c-detector-setfit-stage2a-scaffold.md).

## Контракт модуля `onec_setfit_gate.py`
`setfit_prob(text, model=None) -> float ∈ [0,1] | None`
- `None` ⟸ `ONEC_SETFIT_ENABLE` не задан ∨ нет `setfit` ∨ нет модели ∨ ошибка → caller падает на TF-IDF.
- module-level = ТОЛЬКО stdlib; `import setfit`/torch — лениво в `_load_model()` (импорт из хука дёшев).
- `_positive_prob`: метки [0,1] → последний столбец `predict_proba` = P(is_1c).
- env: `ONEC_SETFIT_ENABLE`, `ONEC_SETFIT_MODEL_DIR` (деф. `models/onec-setfit/`), `ONEC_SETFIT_THRESHOLD` (0.5).

## Интеграция `route_1c_task`
`_semantic_signal(prompt) -> (score, source, hit)`: SetFit (opt-in) → при `None` TF-IDF. Порог свой на
источник (вероятность vs косинус — разные шкалы). Новый ключ `semantic_source ∈ {setfit, tfidf, skipped}`.
**Behavior-preserving:** гейт выключен (дефолт) ⇒ поведение идентично прежнему.

## Данные/обучение
`train_onec_setfit.py` поверх `data/1c-detector-ground-truth.json` (is_1c = таргет). `--dry-run` валидирует
без deps. Калибровка — `eval_1c_detector.py --setfit`. Разметка: silver из regex-high-conf + ручная hard-граница.

## Инвариант безопасности
SetFit = МЯГКИЙ сигнал → промоут только `ask_1c`, никогда confident/auto. Blast-radius безопасен.
