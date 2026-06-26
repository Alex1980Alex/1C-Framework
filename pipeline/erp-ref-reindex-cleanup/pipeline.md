# Пайплайн: Диагностика и чистый rebuild ERP-эталона (`bsl_code_erp_ref`)

Тип: infra / RAG ops (не 1С-разработка — BSL не писался). Trivial-профиль, единый `pipeline.md`.

## 1. План (Планирование)
Вопрос: как прошла индексация `external/1c-reference-src/erp`, на каком этапе.
Цель: установить фактическое состояние коллекции `bsl_code_erp_ref` и довести индекс до корректного.

## 2. Дизайн (одобрено пользователем)
Диагностика (Qdrant + `data/indexing-progress.jsonl` + код индексатора):
- коллекция green / **1 341 006 точек**, но **dense-only** (нет BM25);
- **дубли `C:\` ↔ `D:\`** из-за переезда корня источника (point-ID выводится из `module_path`) — выборка 10k = 42% C: / 58% D:;
- **ни один полный прогон не финишировал** (`run_end` только у smoke); последний завис ~32ч — CUDA-wedge (ADR-038), запускался без супервизора.

Решение (одобрено пользователем «чистый пересоздать»): дроп коллекции → `reindex_supervised.py` (hybrid, stall-watchdog по росту points, `--long-batch1-tokens 1024`, `--max-file-bytes 2МБ`) из **единого** корня `D:\1c-reference-src\erp` → доиндексация 33 deferred-монстров (`--enable-sparse` в уже-hybrid) → restart TEI. Супервизор recreate не делает — дроп вручную.

## 3. Реализация
- Дроп `bsl_code_erp_ref` (1 341 006 → 404 verified), `docker stop pdf-rag-tei`, GPU свободен (3.5/24 ГБ).
- Запущен `reindex_supervised.py` в фоне (run_id `…-2eb4f8`, batch 32) — создаёт hybrid, индексирует `D:\` под watchdog.
- Память: `feedback_reindex_source_root_move_duplicates.md` + указатель в `MEMORY.md` (раздел RAG).

## 4. Тест (pending — после фонового прогона)
По завершении супервизора: status green, layout hybrid (`dense`+`bm25`), финальный count, **отсутствие `C:\`-префиксов** в `module_path` (дубли убраны), 33 монстра доиндексированы; затем `docker start pdf-rag-tei`.
