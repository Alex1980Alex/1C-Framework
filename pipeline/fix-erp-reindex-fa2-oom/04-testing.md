# Этап 4 — Тестирование

## code-verify (bug-fix-validation) — PASS
Ревьюер-субагент подтвердил все 7 пунктов: фикс адресует root cause (linear-memory
attention), не ломает явный `--enable-fa2`/qwen3-tei/late-chunking, escape hatches на месте,
безопасный откат на ABI-сломанный flash-attn, порядок до `make_embedder` корректен,
сообщения ASCII, нет over-engineering. Минорное benign-замечание (двойная проба в редком
пути «явный флаг + проба упала») — не дефект, оставлено. Маркер `[CODE-VERIFY-PASS]`.

## Изолированный smoke (механизм + эквивалентность)
- Qwen3-8B + FA2 загрузился (`attn=flash_attention_2`); god-object **tokens=8192, batch=2**
  → **пик VRAM 17.99 GB allocated / 18.94 GB reserved** из 24 (запас ~5-6 GB). Без FA2
  (`attn=sdpa`) тот же чанк → ~24.2 GB → OOM.
- Эквивалентность: `cosine(FA2, standard) = 0.99990106`, max abs diff `1.465e-3`
  (= bf16 rounding) → **VERDICT: EQUIVALENT (no quality loss)**.

## End-to-end smoke на реальных данных ERP (bounded, throwaway-коллекция)
Команда = боевая + `--limit 300 --buffer-size 64 --no-context --recreate`,
коллекция `bsl_code_erp_ref_smoke`:
- ✅ FA2 авто-включён реальным скриптом (`INFO: auto-enabling FlashAttention-2`,
  `fa2_auto_enabled`, `model_load ... fa2=True`).
- ✅ Пройдена зона смерти старого прогона (chunks 128 → 320), VRAM держался ~20 GB (без OOM).
- ✅ `run_end: chunks=320, errors=0, exit 0`; Qdrant hybrid green (dense 4096d + bm25 sparse).
- Наблюдение: god-object-хвост медленный (батч=1-2 на 8192 + CPU-fastembed BM25), но
  **завершается** — раньше тут был OOM. Информирует ETA full-рана (~30-50ч с перекосом в хвост).

Коллекция и временный smoke-скрипт подчищены.

## Вывод
OOM устранён, качество не затронуто, полный путь model_load → авто-FA2 → чанкинг → эмбеддинг
→ запись в Qdrant подтверждён вживую. Готово к боевому ERP-реиндексу.
