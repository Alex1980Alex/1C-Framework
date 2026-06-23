# 04 Тестирование

## Статика
- ruff + py_compile: PASS (оба скрипта).
- `tests/unit/test_reindex_long_batch1.py` — 4/4 PASS (threshold 0 noop / 1024 / 2048 / порядок).
- supervisor `--help` OK; `_parse_idle` проверен (3m10s=190, 10h35m=38100, 48.2s=48.2).

## Live (Part A — главный proof)
- Прогон `--long-batch1-tokens 1024 --max-file-bytes 2097152 --batch-size 32` (без expandable_segments):
  - max-file-bytes: skipped 33 oversized (deferred-list записан).
  - **Прошёл точку вечного зависания**: points 175615→176127→176639 (+512×2 upsert), file_idx 639→641→644.
  - Тяжёлый файл на batch=1 молотит ~3 мин, но ЗАВЕРШАЕТСЯ (раньше — вечный wedge).
- Контрэксперимент: expandable_segments → завис до первого upsert (подтверждает вред) → откат.

## code-verify
- Reviewer (behavior-preservation + quality-review) по A+B+C: **PASS** (16/16 проверок; 3 некритичных
  замечания, R1 guard пустой лестницы + R3 аннотации применены, R2 косметика).

## Итог
Все 3 части реализованы, проверены, закреплены (ADR-038 + память). Прогон ERP идёт устойчиво.
Доиндексация монстров (33 файла) — `--paths-file data/reports/reindex_deferred.txt --batch-size 1`.
