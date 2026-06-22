# 02 — Дизайн

## Механика (опирается на существующий код, не меняет его)
- `point_id = uuid5(NAMESPACE, f"{collection}-{chunk_id}")` — детерминирован → UPSERT идемпотентен.
- payload `module_path` = `os.path.normpath(module.file_path)` (абсолютный путь).
- файлы: `sorted(project.rglob("*.bsl"))`, `project = args.project.resolve()`.
- delete-stale в конце использует отфильтрованный `bsl_files` → чистит только остаток.

## Изменения
1. Флаг `--skip-indexed` (action=store_true), несовместим с `--recreate` и `--paths` (явные `sys.exit(1)`).
2. Helper `_existing_module_paths(client, collection)` — scroll по коллекции (`with_payload=["module_path"], with_vectors=False`, пагинация по `next_offset`), возвращает set.
3. В блоке file_scan при `--skip-indexed`: `bsl_files = [f for f in bsl_files if os.path.normpath(str(f)) not in done]` + событие `skip_indexed`.
4. В цикле каждые 200 файлов (guard `embedder=="qwen3-st"`): `torch.cuda.empty_cache()` под try/except.

## Граничные случаи
- Пустая/отсутствующая коллекция — `create_collection` идёт ДО scroll → коллекция есть; пустая даёт `([], None)`.
- Файл с 0 чанков (недосброшен при краше) → не в `done` → доделывается.
- Частичный god-object на границе буфера — module-level гранулярность, предупреждение в выводе (R2).

## Одобрение
Approved (auto, постфактум — реализация верифицирована ревьюером).
