# Пайплайн (trivial): Индексация ERP reference-конфига

Операционная задача — запуск семантической векторной индексации эталонного конфига
`external/1c-reference-src/erp` (ERP 2.5.27.52) в Qdrant. Не code-writing; правки файлов —
только заметка в память. Оформлено компактно (ADR-018 trivial-путь).

## План
Пользователь выбрал семантическую индексацию в Qdrant (offline-слои 2+1-lite+3a уже свежие
от 22.06). Цель — коллекция `bsl_code_erp_ref` (hybrid 4096d+bm25) на Qwen3-Embedding-8B,
как в проде.

## Дизайн
`reindex_bsl_qwen3.py --project external/1c-reference-src/erp --embedder qwen3-st
--pooling-mode standard --enable-sparse --collection bsl_code_erp_ref --batch-size 32
--buffer-size 512 --recreate`. Перед запуском `docker stop pdf-rag-tei` (освободить ~16 ГБ VRAM).

## Реализация
3 segfault'а (exit 139) на `model_load` диагностированы (faulthandler + bisect): гонка
daemon-тредов `ProgressTracker` с нативным импортом `sentence_transformers` на стеке
transformers 5.6.2 / ST 5.4.1 / torch 2.10; + отдельный FA2-сегфолт (flash-attn 2.8.3 ABI).
Обход — инлайн runpy-лаунчер, который pre-import'ит torch+ST ДО старта трекера, без `--enable-fa2`.
Прогон запущен через Bash `run_in_background` (переживает ходы). Находка записана в память
`feedback-bsl-reindex-segfault-torch210`.

## Тест
Сквозной пайплайн подтверждён вживую: `model_load DONE 17.6s`, hybrid-коллекция создана
(dense 4096d cosine + bm25 IDF), эмбеддинг идёт (`[bucket] flush=512`), точки пишутся в Qdrant
(points_count растёт, status green; на момент проверки 6 144), GPU 100%. ETA ~30–50ч.
Хвосты: вернуть TEI (`docker start pdf-rag-tei`) по завершении; корневой фикс reindex-скрипта
отдельным ревью (бьёт и прод git-hook реиндекс).
