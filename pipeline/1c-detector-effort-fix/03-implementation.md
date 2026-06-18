# 03 — Кодирование

## Изменённые файлы
1. **`.claude/hooks/shared/pipeline_1c_bridge.py`** (Находка 1):
   - `_EFFORT_CFG["weights"]` += `"develop": 2`.
   - `_EFFORT_CFG["signals"]["develop"]` = `["разработать","реализовать","печатн","механизм","функционал","новую форм","новая форм"]`.
   - `_EFFORT_CFG["signals"]["cross"]` += `"настроить обмен","обмен с баз","обмен между"`.
   - `estimate_effort`: группа `develop` добавлена в цикл подсчёта `pos`.
   - **is_1c / confidence НЕ тронуты** → детект 1С байт-идентичен (проверено: F1=0.974 на исходных 230).
2. **`scripts/eval_1c_detector.py`** (Находка 3):
   - `_BANDS = ("simple","medium","complex")`.
   - `evaluate()`: аккумуляторы `band_tot/band_ok/band_confusion/auto_misroutes`; полоса считается только
     на confident-строках с GT-меткой `complexity`; `auto_misroute` = GT medium/complex при `flow=auto`.
   - Ключ отчёта `complexity_band` (+ человеко-секция с ⚠ auto-мисроутами).
3. **`data/1c-detector-ground-truth.json`**:
   - `complexity` на 35 confident-строк (Находка 3), signal-grounded + 2 домен-суждения (semantic-gap).
   - +18 русскоязычных dev-негативов `source="framework-dev-neg"` (Находка 4).
4. **`tests/unit/test_pipeline_1c_bridge.py`**: 4 регресс-теста (develop-группа, печатные формы ≠ auto,
   обмен ≠ auto, truly-cosmetic всё ещё auto).

## OUT (задокументировано в 02-design)
- Находка 6 (мёртвый light) — нулевой эффект на маршрут, не трогаем.
- Находка 2 (ужесточение `_1C_SIGNAL`) и мульти-подсчёт групп — отдельный срез (риск recall / регресс).
