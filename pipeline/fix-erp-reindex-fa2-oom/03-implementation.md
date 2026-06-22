# Этап 3 — Кодирование

## Изменения
Файл [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py) (коммит `ce5217899`):

1. **Авто-включение FA2** ([~1690](../../scripts/reindex_bsl_qwen3.py#L1690)) — новый блок
   в `main()` после preflight-блока явного `--enable-fa2`, перед late-chunking-гейтом:
   для `qwen3-st` без явного флага и без `BSL_NO_AUTO_FA2` запускает
   `_fa2_preflight_ok()`; PASS → `args.enable_fa2 = True` + `_evt("fa2_auto_enabled")`;
   FAIL → WARNING + `_evt("fa2_auto_enable_failed", action="continue_no_fa2")` (ран не падает).

2. **VRAM-комментарий docstring** ([~331](../../scripts/reindex_bsl_qwen3.py#L331)) —
   исправлено заблуждение «8192 без FA2 safe by ~2GB»: добавлено, что оценка игнорировала
   O(n²)-матрицу скоров `[batch,heads,seq,seq]`, god-object OOM'ит карту, FA2 даёт linear-память
   и теперь авто-включается.

## Переиспользовано (без дублирования)
`_fa2_preflight_ok()` (изолированная subprocess-проба), `_evt()` (телеметрия),
env-флаги `BSL_FORCE_FA2`/`BSL_NO_AUTO_FA2`. Конструктор `Qwen3STEmbedder` уже умел
`enable_fa2 → attn_implementation="flash_attention_2" + padding_side="left"` — правки в нём не нужны.

## Объём
Один if-блок + правка docstring. Без левых изменений. `py_compile` + `ruff check` — чисто.
