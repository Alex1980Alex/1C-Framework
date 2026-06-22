# Этап 2 — Дизайн реализации

## Подход
Авто-включать FA2 для `qwen3-st`, когда `_fa2_preflight_ok()` проходит — вместо того,
чтобы давать standard-pooling реиндексу молча уйти в OOM на god-object. Точка вставки —
в `main()`, сразу ПОСЛЕ существующего блока preflight явного `--enable-fa2` и ПЕРЕД
блоком late-chunking-гейта (чтобы авто-включённый FA2 долетел до всех downstream-проверок
и до `make_embedder`).

## Логика
```
if embedder == "qwen3-st" and not args.enable_fa2 and not BSL_NO_AUTO_FA2:
    if BSL_FORCE_FA2 or _fa2_preflight_ok():
        args.enable_fa2 = True            # → attn_implementation="flash_attention_2"
        _evt("fa2_auto_enabled", ...)     #   + tokenizer padding_side="left" (C6)
    else:
        warn(...); _evt("fa2_auto_enable_failed", action="continue_no_fa2")
```

## Инварианты безопасности
- **Точность**: FA2 — exact-алгоритм → embeddings эквивалентны (не аппроксимация).
- **Откат**: проба упала (ABI-дрифт) → FA2 НЕ включается, ран продолжается (не убиваем многочасовой прогон).
- **Escape hatches**: `BSL_NO_AUTO_FA2=1` (форс legacy), `BSL_FORCE_FA2=1` (обход пробы),
  явный `--enable-fa2` (своя ветка выше — авто-блок её не трогает, двойной пробы нет).
- **qwen3-tei не затронут** (FA2 у него в Rust-рантайме; гард `embedder == "qwen3-st"`).
- Сообщения print строго ASCII (Windows cp1251 консоль).

## Сопутствующее
Поправить вводящий в заблуждение VRAM-комментарий docstring класса (утверждал «8192 без
FA2 safe by ~2GB» — игнорировал O(n²)-скоры; именно там god-object и OOM'нул).

## Решение / approve
Дизайн одобрен (см. approve в state). Единственный hard-гейт пайплайна — дизайн перед
кодированием — закрыт.
