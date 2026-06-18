# 01 — Планирование архитектуры

**Задача:** SetFit как обучаемый слой ② детектора 1С (stage-2a′), opt-in каркас.
**Решение зафиксировано:** [ADR-025](../../.claude/skills/architecture-research/adr/025-1c-detector-setfit-stage2a-scaffold.md).

## Проблема
Семантический слой ② детектора (`route_1c_task`, входы confidence<0.7) — TF-IDF
(`onec_semantic_fallback`). Потолок: bag-of-words не различает near-domain по смыслу. Frozen-подходы
исчерпаны: TEI-эмбеддинги коллапсируют (ADR-023), LLM-on-tail net-neutral на доступной модели (ADR-024).
ADR-024 §Активации п.2 называет SetFit масштабным путём (контрастный fine-tuning адаптирует пространство).

## Размещение в каскаде
① regex (`classify_1c_task`) → confidence · РАЗВИЛКА ≥0.7 · **② SetFit-гейт (opt-in) → откат TF-IDF** ·
③ `estimate_effort`. Слой ② промоутит лишь в `ask_1c` (инвариант: мягкий сигнал, не confident/auto).

## Решения (из ADR-025)
- SetFit подключён **opt-in, по умолчанию спит**; graceful → TF-IDF; текущий каскад не ломается.
- Бинарный is_1c (не мультикласс); сложность остаётся за `estimate_effort`.
- Старт `rubert-tiny2` (RU-native, 29M); апгрейд `multilingual-e5-small`; MiniLM-L12-v2 отклонён.
- Активация: разметка ~150–300 (GT сейчас 68) → train → калибровка → `ONEC_SETFIT_ENABLE=1`.
