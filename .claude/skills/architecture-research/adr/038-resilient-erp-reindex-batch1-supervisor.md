# ADR-038: Устойчивый ERP-reindex — batch=1 для длинных чанков + супервизор + deferred no-loss

**Дата:** 2026-06-24
**Статус:** accepted
**Исследование:** live-диагностика (сессия 2026-06-23/24), [exp]

## Контекст

Реиндекс эталонной ERP (`external/1c-reference-src/erp`, 26 207 `.bsl`) в коллекцию
`bsl_code_erp_ref` (qwen3-st, Qwen3-Embedding-8B 4096d + BM25 hybrid) **застревал** на
~35 % (175 k чанков, 8 270 файлов). Прогон висел 10.5 ч: idle монотонно рос, `file_idx`
заморожен, GPU VRAM 24.2/24.5 GB, **без OOM-исключения и без traceback**.

Живая диагностика (реплика списка файлов индексатора + анализ bucket-флашей):
- **Не случайный VRAM** — детерминированный «тихий CUDA-wedge»: Qwen3-Embedding-8B (~16 GB
  FP16) на 24 GB-карте **заклинивает** (kernel hang, не OOM) при эмбеддинге батча длинных
  чанков **тяжёлого модуля**. Триггерят и `>2MB` монстры (ERP содержит `.bsl` до **10 MB** —
  регламентотчётность/документооборот ФНС), и **крупные `<2MB`** (напр. 621 KB
  `РасчетСебестоимостиПодготовкаДанных` — 7562 строки). Сигнатура флаша перед зависанием:
  `b8=460 max_tok=8192` (кластер max-длины чанков на batch=8).
- **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` ВРЕДИТ** — перебивает заданный самим
  скриптом тюнинг `garbage_collection_threshold:0.6,max_split_size_mb:512` (`os.environ.setdefault`
  не переопределит уже выставленную env) → завис ещё ДО первого upsert. Откат обязателен.
- Зависший CUDA-kernel **нельзя прибить из того же процесса** → in-process per-file timeout
  невозможен; нужен внешний супервизор.

## Решение

Трёхкомпонентный устойчивый reindex (всё аддитивно, дефолты = прежнее поведение):

**Part A — профилактика (главное).** Флаг `--long-batch1-tokens N` (`reindex_bsl_qwen3.py`):
чистый хелпер `_long_batch1_buckets(buckets, N)` форсит **batch=1** для bucket'ов с
`upper > N` (короткие чанки сохраняют быстрый batch). Прокинут через
`Qwen3STEmbedder.__init__` → `make_embedder` → `main`. Рекоменд. `N=1024` (длинные ~8 %
чанков → batch=1, 88 % коротких быстрые). **Live-проверено:** файл, висевший вечно, прошёл
(points 175615→176639, file_idx 639→644; тяжёлый файл на batch=1 молотит ~3 мин, но
**завершается**). [own]

**Part B — сетка безопасности.** `scripts/reindex_supervised.py`: запускает reindex (resume),
следит за **ростом числа точек** в коллекции (POST Qdrant `/points/count`); если индекс не растёт
дольше `--stall-limit` (1500 с/25 мин) → kill дерева (`taskkill /T /F`) → перезапуск с **меньшим
batch (лестница 32→8→1)** + малый буфер (частые флаши = видимый рост). `--skip-indexed` сохраняет
прогресс; batch=1 гарантированно не виснет. **Важно (фикс 2026-06-24):** liveness меряется по росту
points, а НЕ по heartbeat-`idle` — при batch=1 один тяжёлый файл/флаш легитимно идёт >20 мин, и idle
давал ЛОЖНЫЙ wedge (убивал рабочий прогон: points росли 186 879→199 679, а супервизор трижды убил по
idle>1200 с). Эскалация batch выбрана вместо poison-by-path: буфер копит чанки нескольких файлов
(нечёткая атрибуция), а resume+меньший batch проще и надёжнее.

**Part C — no-loss.** `--max-file-bytes` (добавлен ранее) теперь пишет пропущенных монстров
в `data/reports/reindex_deferred.txt` (OSError-safe). Флаг `--paths-file FILE` вливает список
в `--paths` (обход argv-лимита Windows) → доиндексация монстров отдельным проходом
`--paths-file <deferred> --batch-size 1`. Ничего не теряется: всё индексируется в два эшелона
(быстрый основной + batch=1 retry).

## Последствия

### Положительные
- Истинный wedge больше не вешает прогон навсегда (live-proof Part A; Part B переживает
  остаток).
- 100 % покрытие: монстры/тяжёлые файлы доиндексируются batch=1 (no-loss).
- Полностью аддитивно, behavior-preserving (дефолт 0 / OFF), реверсивно. Прод git-hook
  (qwen3-tei, инкрементальный) не затронут.

### Отрицательные
- Медленнее на тяжёлых файлах (batch=1 ~3 мин/файл) → общий wall-clock ERP больше.
- Супервизор Windows-специфичен (`taskkill`).

## Альтернативы

- **`expandable_segments`** — ОТКЛОНЕНО: вредит (перебивает тюнинг аллокатора, завис до
  upsert).
- **Глобальный `--batch-size 1`** — ОТКЛОНЕНО: ×32 медленнее на 88 % коротких чанков (Part A
  бьёт только длинные).
- **Poison-by-path skip-list** — ОТКЛОНЕНО: нечёткая атрибуция (буфер across-files);
  batch-эскалация + resume проще/надёжнее.
- **TEI вместо in-process qwen3-st** — не рассматривалось в этой итерации (отдельный backend).

## Связанные файлы

- `scripts/reindex_bsl_qwen3.py` — Part A (`_long_batch1_buckets`, `--long-batch1-tokens`),
  Part C (`--max-file-bytes` deferred-list, `--paths-file`).
- `scripts/reindex_supervised.py` — Part B (новый супервизор).
- `tests/unit/test_reindex_long_batch1.py` — юнит-тест Part A (4 кейса).
- Память: `feedback_qwen3_embedding_wedge_heavy_modules` (≠ load-time
  `feedback_bsl_reindex_segfault_torch210`).
- Пайплайн: `pipeline/erp-reindex-watchdog/`.
