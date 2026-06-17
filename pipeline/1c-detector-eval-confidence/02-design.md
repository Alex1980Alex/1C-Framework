# 02 — Дизайн: golden-set eval-харнесс (#1) + калиброванная уверенность (#2)

## #1 Golden-set eval-харнесс (клон `eval-skill-router.py`)
**Артефакты:** `data/1c-detector-ground-truth.json` (массив) + `scripts/eval_1c_detector.py`.

GT-схема (заземлено на реальные ТЗ `configuration/260304…/docs` + чат-диалоги + негативы):
```json
{"text": "...", "is_1c": true|false, "route_class": "none"|"ask"|"confident", "source": "...", "split": "train"|"test"}
```
- `route_class`: `none`=не 1С (`flow=none`) · `ask`=1С слабый (`flow=ask_1c`) · `confident`=1С сильный (`flow∈{auto,ask_flow,gated}`).
- **JSON-массив, не .jsonl**: `.json` exempt от code-skill-enforcer (.jsonl — нет), а GT несёт 1С-токены (`Документ `/`гкс_`), которые иначе ловит Level A.1 → learning-loop.

`scripts/eval_1c_detector.py` — **in-process** (importlib `pipeline_1c_bridge`, без subprocess — функции чистые):
- метрики `is_1c` (P/R/F1, positive=1С) — ядро;
- `route_class` accuracy + confusion (none/ask/confident);
- **confidence-сепарация** (после #2): mean `confidence` по классам — confident должен быть отделён от ask/none;
- честный train/test split (поле `split` ∨ sha1%5), pooled — диагностический (детектор не учится на GT);
- `--json`/`--split`/`--cv K`/FP-FN surfacing. Паттерн `_action_f1`/`_split_of` из skill-router.

## #2 Калиброванная уверенность (вместо бинарной)
В `pipeline_1c_bridge.py` — функция `confidence_score(prompt, cl)` → 0..1 (max по сигналам):
| Сигнал | Скор |
|---|---|
| JIRA | 1.0 |
| `_1C_CODE` (литеральный код) | 0.9 |
| `_1C_DEFINITIVE` (гкс_/configuration) | 0.9 |
| `_1C_STRONG` (объект.точка/CamelCase) | 0.7 |
| `_1C_SIGNAL`+глагол (без strong) | 0.5 |
| не 1С | 0.0 |

**Backward-compat (инвариант):** `confident_1c = confidence >= 0.7` — точно воспроизводит текущее `jira ∨ strong ∨ code` (jira1.0/code0.9/гкс_0.9/strong0.7 ≥0.7 → confident; signal+verb0.5 <0.7 → ask_1c). Все 48 unit-тестов целы. `confidence` экспонируется в `classify`/`route` (для будущей #3 fall-through на mid-band).

## Тест-план
- baseline eval ДО #2 → зафиксировать P/R/F1 + route-accuracy.
- после #2: eval БЕЗ изменения is_1c/route-метрик (behavior-preserving) + confidence-сепарация измерима + 48 unit зелёные + новые unit на `confidence_score`.
- code-verify (reviewer), коммит.
