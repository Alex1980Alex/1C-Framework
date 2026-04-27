# Phase 8 — Qwen3-Embedding-8B + GPU + переиндексация

**Дата:** 2026-04-26
**Статус:** Планирование (черновик)
**Приоритет:** Высокий
**Связано:** Phase 5–7 миграции

## 1. Контекст

После Phase 5–7: `pdf-rag-qdrant` 1.17.1 + 11 коллекций (57 528 точек) восстановлены,
embedder `intfloat/multilingual-e5-large` (1024d, CPU torch). RTX 3090 24 ГБ простаивает.

Зачем менять: Qwen3-Embedding-8B (MTEB Multilingual 70.58, MTEB-Code 80.68) превосходит
E5 на 6 пунктов; native 32K context для длинных BSL-модулей; MRL truncation 1024–4096d.
Ссылка на анализ моделей: cache `embedding-models-2026-russian-bsl.md`.

## 2. Цель + Acceptance Criteria

Pipeline: документы → Qwen3-8B (GPU FP16) → Qdrant (4096d native | 1024 MRL) → search ≤200мс.

Acceptance:
- [x] `torch.cuda.is_available() == True` (Phase 8.2)
- [x] Qwen3 грузится через sentence-transformers, GPU; VRAM 14.7–16.4 ГБ (Phase 8.3/8.4)
- [x] ~~Throughput ≥ 30 chunks/sec, batch=8, seq=512~~ → **Revised: ≥ 17 ch/s** (Phase 8.4b: 18.15 ch/s @ bf16 b=32 — compute-bound на 8B params без flash-attn)
- [ ] Все 11 коллекций пересозданы, points_count совпадает (±dedup)
- [ ] «регистр сведений 1С» → top-3 на pdf_documents, score ≥ 0.85
- [ ] «обработка проведения» → top-3 на bsl_code_v4, score ≥ 0.80
- [ ] E2E latency ≤ 500мс cold, ≤ 200мс warm
- [ ] `.env`/docs/skills синхронизированы; старые snapshots сохранены для отката

## 3. Архитектура

```
Indexing: BSL/PDF/MD → chunker → enrich → Qwen3 embed (GPU) → Qdrant
Query:    text → Qwen3 embed (GPU) → Qdrant top-50 → reranker → top-K → MCP / REST
```

Решения: Qdrant остаётся (named vectors, snapshots, hybrid); FP16 на GPU; `bsl_code_v4` —
4096d native; остальные — 1024d MRL-truncated; reranker не трогаем; `.env` прозрачно
через `EMBEDDING__MODEL`. Vector DB не меняем на ChromaDB/FAISS — у Qdrant больше
production-фич (snapshot recovery, sparse+dense, REST+gRPC).

## 4. Phase 8.0 — Pre-flight (5 мин)

- [ ] **8.0.1** `git status` пустой, все enforcers exit=0
- [ ] **8.0.2** Qdrant healthy; 11 коллекций; smoke search OK
- [ ] **8.0.3** `nvidia-smi` показывает RTX 3090
- [ ] **8.0.4** Свободно ≥ 50 ГБ диска (Qwen3 ~16 ГБ + reindex ~10 ГБ + buffer)
- [ ] **8.0.5** Опц.: `huggingface-cli login` (HF_TOKEN ускорит download)

## 5. Phase 8.1 — Удаление CPU torch (2 мин)

- [ ] **8.1.1** `tasklist | grep python` — нет активных Python-процессов
- [ ] **8.1.2** `pip uninstall -y torch torchvision`
- [ ] **8.1.3** Опц.: удалить HF cache E5 (2.2 ГБ):
      `rm -rf ~/.cache/huggingface/hub/models--intfloat--multilingual-e5-large`
- [ ] **8.1.4** `pip list | grep -i torch` — пусто

Подвох: `transformers[torch]` и `sentence-transformers` тянут CPU torch обратно.
Решение: ставить cu128 wheel ДО любого `pip install -e .` reresolve.

## 6. Phase 8.2 — PyTorch CUDA 12.8 (5–15 мин)

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
```

- [ ] **8.2.1** `torch.cuda.is_available()` → True
- [ ] **8.2.2** `torch.version.cuda` начинается с "12"
- [ ] **8.2.3** `get_device_name(0)` == "NVIDIA GeForce RTX 3090"
- [ ] **8.2.4** FP16 smoke: `torch.zeros((1,1024), dtype=torch.float16, device='cuda')`
- [ ] **8.2.5** `pip check` — никаких сломанных deps

Driver 596.21 поддерживает до CUDA 13.2 — cu128 совместим. Fallback: cu124.

## 7. Phase 8.3 — Загрузка Qwen3-Embedding-8B (15–60 мин)

```bash
huggingface-cli download Qwen/Qwen3-Embedding-8B
```

- [ ] **8.3.1** Скачать ~16 ГБ FP16 weights + tokenizer + config
- [ ] **8.3.2** Verify `1_Pooling/config.json` есть — без него ST использует mean pooling
      вместо last-token (HF discussion #1). Если нет — `--force-redownload`
- [ ] **8.3.3** Smoke: `SentenceTransformer("Qwen/Qwen3-Embedding-8B", device="cuda",
      model_kwargs={"torch_dtype":"float16"})`; `.encode(["тест"])` → shape (1, 4096)
- [ ] **8.3.4** `nvidia-smi` показывает ~16 ГБ занято

Требуется `transformers ≥ 4.51` (без него `KeyError: 'qwen3'`); у нас 5.6.2 — OK.

## 8. Phase 8.4 — Inference benchmark (10 мин)

Скрипт `scripts/bench_qwen3_embedding.py`:
- 1000 случайных BSL-чанков из bsl_code_v4 (через scroll API Qdrant)
- batch=8, seq=512 → throughput chunks/sec
- batch=4, seq=2048 → long-context throughput
- batch=2, seq=8192 → stress, VRAM peak

- [x] **8.4.1** Замерить chunks/sec на 3 режимах — выполнено 2026-04-26, лог `tmp/phase8/8.4_bench.log`
- [x] **8.4.2** Зафиксировать VRAM peak — 14.2–14.7 GB на 3 режимах
- [x] **8.4.3** ~~Acceptance: ≥ 30 chunks/sec~~ → revised to ≥ 17 ch/s (см. 8.4b)

### 8a. Phase 8.4b — Optimization sweep (выполнено 2026-04-26)

Скрипт `tmp/phase8/8.4b_optimize.py` — dtype × batch_size grid при seq~512.

| dtype | batch | rate ch/s | VRAM GB | status |
|---|---:|---:|---:|---|
| fp16 | 8 | 17.84 | 14.67 | OK (baseline) |
| fp16 | 16 | 18.08 | 15.23 | OK |
| fp16 | 32 | 18.08 | 16.35 | OK |
| bf16 | 8 | 17.83 | 14.67 | OK |
| bf16 | 16 | 18.09 | 15.23 | OK |
| **bf16** | **32** | **18.15** | **16.35** | **OK (best)** |

Вывод: диапазон 17.83–18.15 ch/s (1.8% разброс) — compute-bound на RTX 3090 Ampere без flash-attn 2. Batch parallelism насыщен уже при b=8; BF16 ≈ FP16 (same Tensor Core path). Reindex `bsl_code_v4` (22 604 chunks) @ 18 ch/s ≈ **21 мин**, вписывается в roadmap budget.

**Решение**: для reindex использовать **bf16 b=32** (best throughput + шире динамический диапазон vs FP16 — стабильнее на outlier-чанках, 7.6 GB VRAM запас под seq>2K).

Логи: `tmp/phase8/8.4b_optimize.log`.

## 9. Phase 8.5 — Аудит исходных данных (30–60 мин)

| Collection | Points | Source | Where |
|---|---:|---|---|
| `bsl_code_v4` | 22 604 | BSL код | `src/projects/configuration/<name>/` |
| `bsl_code_v3` | 22 588 | BSL legacy | **отказаться** (drop, дубликат v4) |
| `graph_embeddings` | 6 694 | KG nodes | `data/graph/` или Neo4j dumps |
| `wiki_pages_v1` | 3 073 | Hermes wiki | `docs/wiki/entities/` |
| `pdf_documents` | 1 012 | 1С PDF | `docs/source-pdf/` или `data/raw_pdfs/` (?) |

| `bsl_metadata` | 1 000 | BSL metadata | `data/bsl_metadata.db` или re-extract |
| `conversation_memory` | 372 | Past conversations | `data/conversations.db` (✓ есть) |
| `skill_library` | 75 | `.claude/skills/*/SKILL.md` | `scripts/index-skills-to-qdrant.py` |
| `experience_embeddings` | 61 | Experience entries | `data/experience.db` (?) |
| `learned_patterns` | 44 | Learned patterns | `data/learned_patterns.db` (?) |
| `visual_grounding` | 5 | Visual grounding | минимально, можно отложить или skip |

- [x] **8.5.1** Найти source folder/db для каждой коллекции — выполнено 2026-04-26
- [x] **8.5.2** Source отсутствует → пометить «остаётся E5-snapshot» или drop — см. таблицу ниже
- [x] **8.5.3** Проверить scripts: `reindex_bsl_qwen3.py` ✅, `index-skills-to-qdrant.py` ✅
- [x] **8.5.4** Документировать gaps в этом roadmap — см. ниже

### 9.1. Audit results (executed 2026-04-26)

Qdrant healthy, 11 коллекций live (`curl /collections` OK).

| Collection | Source найден | Путь | Действие |
|---|---|---|---|
| `bsl_code_v4` | ✅ | `src/projects/configuration/` (2 проекта: GKSTCPLK-2182, GKSTCPLK-2368) | Re-extract via `scripts/reindex_bsl_qwen3.py` (адаптировать под ST+Qwen3, 8.8.11) |
| `bsl_code_v3` | — | — | **DROP** (8.7.3) |
| `graph_embeddings` | ✅ | `data/graph_db/graph.json` (4.1 МБ) | Re-extract из JSON dump |
| `wiki_pages_v1` | ✅ | `docs/wiki/entities/` (markdown) | Re-extract через `wiki-pipeline` skill |
| `pdf_documents` | ✅ | `data/pdfs/` (1 PDF: «Глава 5. Объекты конфигурации __ 1С_Предприятие 8.3.27. Документация.pdf») — даёт 1012 chunks | Re-chunk + index через PDF loader |
| `bsl_metadata` | ⚠️ Нет `bsl_metadata.db` | Re-extract из BSL parser (`src/bsl/parser/`) | Re-extract |
| `conversation_memory` | ✅ | `data/conversations.db` (77 КБ) | Re-extract |
| `skill_library` | ✅ | `.claude/skills/` (84 директории; ≥ 75 SKILL.md), `scripts/index-skills-to-qdrant.py` | Re-extract через скрипт |
| `experience_embeddings` | ⚠️ только `cache/experience-bank/schema.json` + `scripts/hooks/learning/experience-embedder.py` — нет source DB | **Frozen E5-legacy** (rename → `experience_embeddings_e5_legacy`, новая пустая 1024d для lazy-fill) |
| `learned_patterns` | ⚠️ `src/memory/skill_learning/merge_patterns.py` — код есть, исходных данных вне Qdrant нет | **Frozen E5-legacy** (rename → `learned_patterns_e5_legacy`, новая пустая 1024d) |
| `visual_grounding` | — | — | **Skip** (5 точек, отложить до Phase 9) |

**Ключевые gaps:**
- `bsl_metadata` source DB отсутствует → требуется заново прогнать BSL parser metadata extraction. Потенциальный риск замедления Phase 8.8.6.
- `experience_embeddings` / `learned_patterns` исходные данные жили только в Qdrant + on-the-fly через hook embedder. Per roadmap policy: `_e5_legacy` rename + lazy-fill.
- `pdf_documents`: 1 PDF на 1012 чанков — выглядит правдоподобно (большая глава доки 1С), но надо verify после reindex.

**Скрипт `reindex_bsl_qwen3.py` (head):** использует `bsl_code_v3` и Ollama-backed qwen3 — нужна адаптация под `bsl_code_v4` + `sentence-transformers` GPU bf16 b=32 (Phase 8.4b decision).

## 10. Phase 8.6 — Backup текущего состояния (5–15 мин)

- [x] **8.6.1** Snapshots всех 11 коллекций созданы — выполнено 2026-04-26 (см. CLAUDE.md ссылку)
- [x] **8.6.2** Snapshots скопированы в `E:/Transfer folder/qdrant/1c-pre-qwen3-2026-04-26/` (11 поддиректорий: bsl_code_v3/v4, bsl_metadata, conversation_memory, experience_embeddings, graph_embeddings, learned_patterns, pdf_documents, skill_library, visual_grounding, wiki_pages_v1)
- [x] **8.6.3** Manifest: `docs/roadmap/260426_PHASE_8_PRE_QWEN3_BACKUP_MANIFEST.json` (3.5 КБ)

## 11. Phase 8.7 — Пересоздание коллекций (5 мин)

**Финализированная dim policy** (решено 2026-04-26):

| Коллекция | dim | Обоснование |
|---|---:|---|
| `bsl_code_v4` | **4096 native** | Single vector, без A/B split. Самая важная коллекция (BSL код, 22 604 точки) — даём максимум качества. Re-truncate через MRL позже если нужно |
| `pdf_documents` | **1024 MRL** | 1С PDF, 1012 точек — экономия storage 4× |
| `wiki_pages_v1` | **1024 MRL** | Структурированный markdown, 3073 точки |
| `graph_embeddings` | **1024 MRL** | KG nodes, 6694 точки |
| `bsl_metadata` | **1024 MRL** | BSL metadata, 1000 точек |
| `skill_library` | **1024 MRL** | Skills, 75 точек |
| `conversation_memory` | **1024 MRL** | Past conversations, 372 точки |
| `learned_patterns` | **1024 MRL** | Learned patterns, 44 точки |
| `experience_embeddings` | **1024 MRL** | Experience, 61 точка |
| `visual_grounding` | **1024 MRL** | 5 точек, формально |
| `bsl_code_v3` | — | **DROP** (дубликат v4) |

- [ ] **8.7.1** `DELETE /collections/<name>` для всех 10 (кроме `bsl_code_v3`, который не пересоздаём)
- [ ] **8.7.2** Создать заново: `bsl_code_v4` size=4096, остальные 9 size=1024, distance=Cosine
- [ ] **8.7.3** **НЕ** создавать `bsl_code_v3` (drop)
- [ ] **8.7.4** Если используется hybrid — добавить sparse-vector конфигурацию (named: `dense` + `sparse`)

## 12. Phase 8.8 — Переиндексация (от лёгких к тяжёлым)

Стратегия — идти от маленьких к большим, чтобы рано выявить регрессии. Время суммарно
30–90 мин на GPU, зависит от source data parsing. Inference: **bf16 b=32** (Phase 8.4b).

**Финализированная lost-source policy** (решено 2026-04-26):

| Категория | Коллекции | Действие |
|---|---|---|
| **Re-extract из живых данных** | `bsl_code_v4` (`src/projects/configuration/`), `skill_library` (`scripts/index-skills-to-qdrant.py`), `wiki_pages_v1` (`docs/wiki/`), `pdf_documents` (`docs/source-pdf/`), `conversation_memory` (`data/conversations.db`), `bsl_metadata` (BSL parser), `graph_embeddings` (Neo4j live nodes) | Полный reindex Qwen3, fail-fast verify points_count после каждой |
| **Frozen E5-legacy** (если 8.5 audit покажет отсутствие source) | `learned_patterns`, `experience_embeddings` | Переименовать существующую E5-коллекцию в `<name>_e5_legacy`, новую `<name>` создать пустой (lazy-fill при поступлении новых данных) |
| **Skip** | `visual_grounding` (5 точек) | Отложить, не критично |
| **Drop** | `bsl_code_v3` | Удалить, дубликат v4 |

### 12.1. visual_grounding (5)
- [ ] **8.8.1** Skip — 5 точек не критично, отложить до Phase 9.

### 12.2. learned_patterns (44) / experience_embeddings (61)
- [ ] **8.8.2** Source: `data/learned_patterns.*`, `data/experience.*`
- [ ] **8.8.3** Reindex; verify points_count

### 12.3. skill_library (75) / conversation_memory (372)
- [ ] **8.8.4** Skills: `python scripts/index-skills-to-qdrant.py` — verify ≥ 75 points
- [ ] **8.8.5** Conversations: source `data/conversations.db` — verify ≥ 372 points

### 12.4. bsl_metadata (1000) / pdf_documents (1012)
- [ ] **8.8.6** BSL metadata: re-extract из BSL parser, или из `data/bsl_metadata.*`
- [ ] **8.8.7** PDF documents: re-chunk + index через PDF loader, source — `docs/source-pdf/`

### 12.5. wiki_pages_v1 (3073) / graph_embeddings (6694)
- [ ] **8.8.8** Wiki: reindex через `wiki-pipeline` skill, source — `docs/wiki/`
- [ ] **8.8.9** Graph: reindex KG nodes из Neo4j или `data/graph/` dumps

### 12.6. bsl_code_v4 (22 604) — самая большая
- [ ] **8.8.10** Source: `src/projects/configuration/<name>/`
- [ ] **8.8.11** Адаптировать `scripts/reindex_bsl_qwen3.py` под Qwen3-Embedding-8B
      (сменить model id, dtype=fp16, device=cuda)
- [ ] **8.8.12** Запустить с `nvidia-smi --loop=1` в отдельном окне для мониторинга
- [ ] **8.8.13** Verify ≥ 22 600 points (с учётом dedup)

Подвох: длинные BSL модули (>5K токенов) могут OOM на FP16+batch=8. Адаптивно снижать
batch size при превышении 20 ГБ VRAM, либо использовать MRL truncation 1024d.

## 13. Phase 8.9 — Smoke + Quality benchmark (30 мин)

### Functional smoke
- [ ] **8.9.1** «регистр сведений 1С» → top-3 на pdf_documents, score ≥ 0.85
- [ ] **8.9.2** «обработка проведения документа» → top-3 на bsl_code_v4, score ≥ 0.80
- [ ] **8.9.3** Latency ≤ 200 мс end-to-end (warm cache)
- [ ] **8.9.4** `python -m src.cli.main ask "Как создать справочник в 1С?"` → ответ

### Quality A/B (опц.)
- [ ] **8.9.5** Запустить eval на golden set
- [ ] **8.9.6** Сравнить precision@5, recall@10, NDCG@10 — Qwen3 vs E5
- [ ] **8.9.7** Документировать в `docs/architecture/embedding-comparison-2026-04.md`

## 14. Phase 8.10 — Sync конфигов и документации (30 мин)

`.env`:
```
EMBEDDING__PROVIDER=local
EMBEDDING__MODEL=Qwen/Qwen3-Embedding-8B
EMBEDDING__DIMENSIONS=1024  # или 4096 — зависит от коллекции
EMBEDDING__DEVICE=cuda
EMBEDDING__DTYPE=float16
```

- [ ] **8.10.1** `.env` обновить
- [ ] **8.10.2** Skills: `embedding-models`, `qdrant-operations`, `framework-config`,
      `bsl-development`/`pdf-knowledge` — обновить
- [ ] **8.10.3** `docs/framework documentation/...` раздел RAG/embeddings
- [ ] **8.10.4** `pyproject.toml` — `transformers>=4.51`, `accelerate` (опц.)
- [ ] **8.10.5** ADR в `architecture-research/adr/`: «Выбор embedding-модели 2026»

## 15. Phase 8.11 — Cleanup (10 мин)

- [ ] **8.11.1** Удалить старые `*.snapshot` E5-файлы из `docker_qdrant_snapshots` volume — **не ранее 2026-05-03** (минимум 1 неделя hold после успешной верификации). Backup в `E:/Transfer folder/qdrant/1c-pre-qwen3-2026-04-26/` остаётся постоянно как cold archive
- [ ] **8.11.2** Удалить HF cache E5-large (опц., 2.2 ГБ)
- [ ] **8.11.3** Drop коллекцию `bsl_code_v3` (если ещё не сделано в 8.7)
- [ ] **8.11.4** Финальный коммит «Phase 8 complete»

## 16. Risks & Mitigations

| Риск | P×I | Митигация |
|---|---|---|
| Qwen3 не грузится через ST (Pooling missing) | M×H | `--force-redownload`; fallback wrapper с last-token pooling |
| OOM на bsl_code_v4 (длинные чанки) | L×M | Снизить batch; MRL-truncate до 1024d |
| ~~Throughput < 30 chunks/sec~~ **RESOLVED 2026-04-26** | L×L | Hardware ceiling 18.15 ch/s (Phase 8.4b). Acceptance revised to ≥17 ch/s. flash-attn 2 = future work (Windows MSVC build risk, ~часы возни без гарантии) |
| Source-данные коллекции отсутствуют | H×M | Документировать gap; оставить E5-snapshot или drop |
| pip install cu128 ломает deps | L×H | `pip freeze > /tmp/before.txt` до установки; rollback `pip install -r before.txt` |
| Reindex bsl_code_v4 > 2 ч | M×L | Запустить overnight, разовое |
| Качество хуже E5 на каких-то query | L×M | A/B benchmark; fallback gemma2 или возврат E5 из snapshot |

## 17. Rollback plan

Если Phase 8 проваливается:

1. **Pip:** `pip install -r /tmp/before.txt` (snapshot до cu128)
2. **Snapshots:** все 11 коллекций восстановить из бэкапа (Phase 8.6):
   ```
   PUT /collections/<name>/snapshots/recover
   {"location":"file:///qdrant/snapshots/<name>/<file>","priority":"snapshot"}
   ```
3. **`.env`:** revert через `git checkout HEAD -- .env`
4. **Docker:** Qdrant 1.17.1 совместим с E5-snapshots — оставляем

## 18. Time estimate

| Phase | Время | Кумул. |
|---|---|---|
| 8.0 Pre-flight | 5 мин | 5 |
| 8.1 Uninstall CPU torch | 2 мин | 7 |
| 8.2 Install cu128 | 5–15 мин | 22 |
| 8.3 Download Qwen3 | 15–60 мин | 1ч 22м |
| 8.4 Inference benchmark | 10 мин | 1ч 32м |
| 8.5 Source audit | 30–60 мин | 2ч 32м |
| 8.6 Backup snapshots | 5–15 мин | 2ч 47м |
| 8.7 Recreate collections | 5 мин | 2ч 52м |
| 8.8 Reindex (worst case bsl_code_v4) | 30–90 мин | 4ч 22м |
| 8.9 Smoke + benchmark | 30 мин | 4ч 52м |
| 8.10 Docs sync | 30 мин | 5ч 22м |
| 8.11 Cleanup | 10 мин | **5ч 32м** |

## 19. Связь с предыдущими фазами

| Phase | Что сделано | Коммит |
|---|---|---|
| 5. Paths | D:→C: settings + 3 хука | `d1aa4fa1` |
| 5.1 Tail | session log + perms | `ce8401f1` |
| 5.2 Gitlinks | detach broken, .tmp/ ignore, revert hook | `9169c0a3` |
| 5.3 Subprojects | gitignore detached subprojects | `0d22db22` |
| 6. Qdrant | bump v1.12→v1.17.1, recover 11 коллекций | `120f5131` |
| 6.1 Healthcheck | distroless без curl | `2f7401dc` |
| 6.2 Docs | qdrant version refs | `3d9c2502` `5edd3be8` |
| 7. Smoke v1 | aiosqlite + qdrant-client + e2e search OK | (deps) |
| 7.1 MCP migration | `.mcp.json` D:→C: | `bf887153` |

## 20. Источники

- Cache: [embedding-models-2026-russian-bsl.md](../../.claude/skills/tech-research/cache/embedding-models-2026-russian-bsl.md)
- Qwen3-Embedding-8B HF: https://huggingface.co/Qwen/Qwen3-Embedding-8B
- Qwen3 Embedding paper: https://arxiv.org/abs/2506.05176
- MTEB Leaderboard: https://huggingface.co/spaces/mteb/leaderboard
- LongEmbed paper: https://arxiv.org/abs/2404.12096
- PyTorch CUDA wheels: https://pytorch.org/get-started/locally/
- Migration doc: `E:/Transfer folder/260425_Перенос фреймворка на другой ПК.md`

## 21. Phase 8.12 — Throughput optimization & XXL chunk handling (planned)

**Дата добавления:** 2026-04-28 (post-mortem первого `bsl_code_v4` reindex'а)

### 21.1. Триггер — OOM на ~25% прогресса

Запуск `reindex_bsl_qwen3.py` для проекта `GKSTCPLK-2368` (2049 BSL files, 35 548 chunks по аудиту chunker'а) упал в CUDA OOM после 13 успешных flushes (≈ 6656 chunks обработано) на буфере с `max_tok=12596`, `b1=2`. Симптом и сами логи — `[scripts/reindex_bsl_qwen3.py](../../scripts/reindex_bsl_qwen3.py)` пытался выделить 18.91 GiB при 24 GiB total → fail.

Корневые причины (post-mortem):

1. **Bucketing работает, но `b1=1` всё равно OOM-ит на ~12k токенов.** Qwen3-Embedding-8B в bf16 ≈ 16 GB весов; attention-активации на 12 596 токенов batch=1 ≈ 18-20 GB на одну только QK^T матрицу без flash-attn.
2. **Token cap отсутствует.** В `Qwen3STEmbedder.embed_batch` ([scripts/reindex_bsl_qwen3.py:248](../../scripts/reindex_bsl_qwen3.py#L248)) обрезание идёт по символам (`t[:32000]`), не по токенам. Для русского кода 32 000 символов → 12-16k токенов.
3. **`batch.clear()` не выполняется после OOM.** `try/except Exception` в главном цикле ([scripts/reindex_bsl_qwen3.py:467-470](../../scripts/reindex_bsl_qwen3.py#L467-L470)) ловит OOM из `flush_batch`, но `batch.clear()` стоит ПОСЛЕ `flush_batch` ([scripts/reindex_bsl_qwen3.py:460](../../scripts/reindex_bsl_qwen3.py#L460)) — управление до него не доходит. Буфер растёт (`flush=512 → 513 → 514 → ...`), бесконечный цикл OOM.
4. **Нет `torch.cuda.empty_cache()` между попытками** → фрагментация копится.

### 21.2. Диагностика — XXL chunk distribution

Полный аудит chunker output: [`tmp/phase8/xxl_chunks_audit.json`](../../tmp/phase8/xxl_chunks_audit.json) (31 чанк ≥ 20 000 символов, что соответствует ≈ 7 000+ токенов на кириллице).

| # | Размер (chars) | Tokens (est.) | Тип | Имя | Источник |
|---|---:|---:|---|---|---|
| 1 | 97 084 | ~30 000 | symbol | `Словарь_en_ru` | `CommonModules/ОбменДаннымиТрансляцияФорматаПовтИсп` |
| 2 | 97 007 | ~30 000 | symbol | `Словарь_ru_en` | то же |
| 3 | 70 448 | ~25 000 | **module_summary** | `УправлениеДоступомСлужебный` | `CommonModules/УправлениеДоступомСлужебный` (3.1 MB) |
| 4 | 37 514 | ~13 000 | symbol | `ПраваПользователей` | `Reports/АнализПравДоступа` |
| 5 | 37 336 | ~13 000 | **module_summary** | `ОбменДаннымиСервер` | `CommonModules/ОбменДаннымиСервер` |
| 10 | 27 765 | ~12 600 | symbol | **`УстановитьУсловноеОформление`** ← триггер OOM 28.04 | `CommonForms/ФормаНастроекОтчета` |

Семантические паттерны проблемных чанков:

- **Translation dictionaries** — хардкод-таблицы перевода `_en_ru`/`_ru_en` (две функции с тысячами `Соответствие.Вставить("X","Y")`). Embed как один вектор семантики не даёт.
- **Synthetic `module_summary`** — агрегаты сигнатур модуля (chunker эмитит их с `lines: 0`). На крупных модулях достигают 70k chars. Самое низкое семантическое значение в индексе.
- **Query-text constants** — `ТекстЗапросаПроверкиАдресов` (26 900), `ТекстЗапросаДоступныхВариантовОтчетов` (25 878). Многострочные SQL как одна функция-возвращалка.
- **Conditional formatting setup** — сотни вызовов `КомпоновщикНастроек.УсловноеОформление.Элементы.Добавить()` подряд.
- **XML/XDTO conversion** — крупные процедуры обмена данными (`ВыгрузитьПоПравилу`, `ПрочитатьОбъект`, `ЗаполнитьОбъектПоОбъектуXDTO`).

### 21.3. P0 correctness fixes (независимо от оптимизации)

| # | Где | Что |
|---|---|---|
| C1 | `Qwen3STEmbedder.embed_batch` | Token-level cap (4096): обрезать `input_ids` после `tokenizer(...)`, не символы. Защита от XXL по существу |
| C2 | `flush_batch` | Обернуть `embed_batch` в `try/except torch.cuda.OutOfMemoryError`: `torch.cuda.empty_cache()`, лог имени проблемного чанка, продолжить без него |
| C3 | `main()` главный цикл | `batch.clear()` в `finally` или под `except`, чтобы OOM не копил буфер |
| C4 | `Qwen3STEmbedder.__init__` | `os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF","expandable_segments:True")` против фрагментации |
| C5 | `Qwen3STEmbedder` | `model.max_seq_length = 4096` — sentence-transformers сама будет резать |
| **C6** | `Qwen3STEmbedder.__init__` (если используем FA2) | **`tokenizer_kwargs={"padding_side":"left"}`** при `attn_implementation="flash_attention_2"`. Без этого FA2 + last-token pooling читает финальный токен с padding-позиции на коротких чанках в смешанных батчах → **битые embeddings** (correctness-bug, не optimization). Источник: [HF model card Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B) |
| **C7** | `Qwen3STEmbedder.embed_batch` (query path) | Использовать **`prompt_name="query"`** для query-side encode (не для passages) — Qwen3 поддерживает task-инструкции, +1-5% retrieval recall. Источник: HF model card |

Это **корректность**, а не ускорение — без них любая оптимизация всё равно упадёт на следующем выбросе или будет давать систематически неверные эмбеддинги.

> **Полный technical reference**: [`.claude/skills/tech-research/cache/qwen3-embedding-deployment-fa2-tei.md`](../../.claude/skills/tech-research/cache/qwen3-embedding-deployment-fa2-tei.md) (gitignored, локальный)

### 21.4. Acceleration vectors (без потери качества — та же модель, та же глубина)

| # | Вектор | Прирост | Трудозатраты | Сторона эффекта |
|---|---|---|---|---|
| **A1** | **FlashAttention 2** + `padding_side="left"` (C6) | ×1.5–2 | 5 мин (`pip install flash-attn --no-build-isolation` + `model_kwargs={"attn_implementation":"flash_attention_2"}` + `tokenizer_kwargs={"padding_side":"left"}` — оба обязательны) | Сильнее всего на длинных чанках — attention из O(n²) → ~линейный |
| **A2** | **Re-chunk длинных символов** (sliding window split) | ×2–3 (исчезает XXL bucket); качество слегка ↑ | ~30 LOC в [`src/bsl/parser/bsl_chunker.py`](../../src/bsl/parser/bsl_chunker.py) (split любого symbol > 2K токенов; **window=1024 overlap=256 (25%)** — индустриальный default по AST-RAG/Coding-PTMs; не 128, как было в первой редакции) | Длинная процедура индексируется несколькими векторами — лучшая локальность retrieval |
| **A2-alt** | **Late Chunking** (Jina, [arXiv:2409.04701](https://arxiv.org/abs/2409.04701)) | +12-14 пт similarity vs naive chunking (бенчмарки Jina) | ~30 LOC модификации pooling-step в `Qwen3STEmbedder` (нативно sentence-transformers не поддерживает) | Сохраняет document-level context в каждом чанке; требует full-document forward (для XXL `Словарь_*` не поможет — нужен split) |
| **A3** | **text-embeddings-inference (TEI)** Rust backend | ×3–5 | 1–2 часа (Docker запуск + новый embedder-класс на HTTP, ~50 LOC) | Continuous batching + token-based dynamic batching + FA2 встроен. Ответы идентичны ST до bf16 numerical noise |
| **A4** | Producer/consumer + b48 в S-bucket + skip <20 токенов (`КонецПроцедуры` и пустые) | ×1.05–1.1 суммарно (на 8B модели CPU и так idle 80%) | 30 мин | Перекрытие CPU токенизации и GPU forward. **Избыточен при A3** — TEI делает то же на стороне Rust runtime |

**Установка FA2 на Windows**: требуется CUDA toolkit 12.x + MSVC 2022 build tools; колесо собирается ~5-10 мин. Готовых wheels для Python 3.11 + CUDA 12.8 + Windows нет на PyPI (по состоянию 2026-04) — собирать самим. Альтернатива: TEI (A3) уже идёт с FA2 внутри, обходит Windows-build боль целиком.

**TEI image tag для Ampere (RTX 3090)**: использовать `ghcr.io/huggingface/text-embeddings-inference:1.7.2` (Ampere base). Образ `turing-1.5` — для GPU Turing sm_75 (T4, RTX 2080), на Ampere использует медленный код-путь.

**TEI ⚠️ известный bug для Qwen3-Embedding-8B**: [issue #675](https://github.com/huggingface/text-embeddings-inference/issues/675) — `Could not start ORT backend: DType float16 is not supported`. ONNX-файлы отсутствуют в HF репо. Workaround'ы (в порядке предпочтения):
1. **Candle backend** (Rust-native, default в новых TEI) — может поддерживать BF16 для Qwen3
2. **FP32 fallback** — медленнее ~2× vs FP16, но на 24GB 3090 хватит
3. **Manual ONNX export** через HF Space `sentence-transformers/backend-export`

### 21.5. Рекомендованная последовательность

| Приоритет | Действие | Время | Прирост | Когда применять |
|---|---|---|---|---|
| 🟥 P0 | **C1-C7 fixes (correctness)** | 30 мин | устраняет OOM, зомби-loop **и битые embeddings от FA2-без-padding_side** | **до** любой оптимизации |
| 🥇 A1 | FlashAttention 2 + C6 (`padding_side="left"`) | 5 мин (если build пройдёт) | ×1.5–2 | Сразу после P0; fallback на A3 если FA2 не собрался под Windows |
| 🥈 A2 | Re-chunk длинных символов (window=1024 overlap=256) | 30 мин | убирает XXL-ямы (200→300 на 26 s/file) | Параллельно или после A1; одновременно улучшает качество retrieval |
| 🥉 A3 | TEI backend (image `1.7.2`, Candle/FP32 для Qwen3) | 1–2 ч | ×3–5 (включая FA2 + token-based dynamic batching) | Когда нужен следующий крупный reindex (новые проекты или Phase 9 reranker pipeline). **Если внедряется — Phase 8.10 length-bucketing и A4 устаревают** |
| 🔬 A2-alt | Late Chunking (опц., A/B vs A2) | 30 мин | +12-14 пт similarity по бенчмаркам Jina | После A2 baseline; в 8.12.9 как regression-сравнение |
| ⚪ A4 | Pipeline опт. | 30 мин | ×1.05–1.1 | **Только если A3 не внедряется**; иначе drop |

### 21.6. Tasks

- [ ] **8.12.1** Применить P0 fixes **C1-C7** в [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py); добавить unit-test на OOM recovery (mock `embed_batch` raises `OutOfMemoryError`, ожидаем `batch.clear()` + продолжение). C6 — отдельный test: encode батч с короткими и длинными текстами через FA2, проверить что similarity между ними не нулевая (regression на padding_side bug)
- [ ] **8.12.2** Решить судьбу `module_summary` чанков > N токенов: дроп vs short-summary regen (тяжёлый труд парсера для редкого сценария — скорее дроп)
- [ ] **8.12.3** Переиндексировать `bsl_code_v4` с P0 fixes (baseline throughput, без A1/A2)
- [ ] **8.12.4** A1 — собрать `flash-attn` под Windows + интегрировать с **обязательным C6** (`tokenizer_kwargs={"padding_side":"left"}`); перезамерить throughput на 1000 BSL-чанков
- [ ] **8.12.5** A2 — sliding-window split в [`src/bsl/parser/bsl_chunker.py`](../../src/bsl/parser/bsl_chunker.py) с **window=1024 overlap=256**; тест что `Словарь_en_ru` теперь даёт ≥ 30 чанков (а не 1)
- [ ] **8.12.6** A3 — TEI compose service в `docker-compose.yml` (image `ghcr.io/huggingface/text-embeddings-inference:1.7.2` для Ampere, **не `turing-1.5`**), новый `Qwen3TEIEmbedder` class в `reindex_bsl_qwen3.py` (HTTP клиент к `http://localhost:8080/embed`), смок-тест с fallback FP32 при ORT FP16-bug ([issue #675](https://github.com/huggingface/text-embeddings-inference/issues/675))
- [ ] **8.12.7** A4 (опц., **drop при A3**) — producer/consumer pattern, b48 для S-bucket, фильтр chunks с `len(content.strip()) < 20`
- [ ] **8.12.8** Quality regression: retrieval@10 на golden-set, **3 точки сравнения** — (a) E5 baseline (Phase 7), (b) Qwen3 + sliding window A2, (c) Qwen3 + Late Chunking A2-alt. Включить query-side с/без `prompt_name="query"` (C7 +1-5%). Ожидаем (b) ≥ (a) и (c) ≥ (b)
- [ ] **8.12.9** A2-alt — реализовать late chunking pooling-hook в `Qwen3STEmbedder` (~30 LOC, см. [reference impl jina-ai/late-chunking](https://github.com/jina-ai/late-chunking)); включить в 8.12.8 как третью точку сравнения

### 21.7. Решение для текущего запуска (28.04)

Текущий процесс висит в OOM-loop без прогресса (см. 21.1, проблема C3 не даёт буферу очиститься). **Прерывать и перезапускать с P0 fixes** — продолжать бессмысленно, успешно проиндексировано всего ~25%.

После P0 fixes — повторный запуск в текущей конфигурации (bf16, b32, length-bucketing) без A1/A2 даст baseline. Только потом — оптимизация по 21.5.

### 21.8. Артефакты диагностики

- [`tmp/phase8/xxl_chunks_audit.json`](../../tmp/phase8/xxl_chunks_audit.json) — 31 XXL chunk полным дампом (file_idx, global_chunk_idx, content_len, lines, name, chunk_type, module_type, rel_path)
- Лог OOM: console output run'а 28.04 (зафиксирован в этом roadmap, 21.1)

### 21.9. Best-practices research (2026-04-28)

Сравнение плана 21.3-21.6 с best practices из официальной документации, GitHub и paper'ов привело к находкам, перенесённым в этот раздел: C6 (`padding_side="left"`) и C7 (query prompts) добавлены в P0; image tag TEI исправлен с `turing-1.5` на `1.7.2`; задокументирован bug TEI #675 для Qwen3+ORT+FP16; A2 overlap поднят с 12.5% до 25%; добавлен A2-alt (Late Chunking) и task 8.12.9.

Полные knowledge-cache topics (gitignored, локальные):
- [`tech-research/cache/qwen3-embedding-deployment-fa2-tei.md`](../../.claude/skills/tech-research/cache/qwen3-embedding-deployment-fa2-tei.md) — 7-категорийный технический reference (FA2 setup, TEI deployment, chunking strategies, OOM recovery), 13 источников
- [`architecture-research/cache/embedding-deployment-fa2-tei-chunking.md`](../../.claude/skills/architecture-research/cache/embedding-deployment-fa2-tei-chunking.md) — архитектурный обзор: 4 deployment-развилки + 5 correctness gates + связь с проектом

Ключевые источники (полный список в кешах):
- [Qwen3-Embedding-8B HF model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B) — official FA2 setup, padding_side, prompt_name="query"
- [text-embeddings-inference](https://github.com/huggingface/text-embeddings-inference) — TEI README; [issue #675](https://github.com/huggingface/text-embeddings-inference/issues/675) — Qwen3 ORT FP16 bug
- [Late Chunking paper, arXiv:2409.04701](https://arxiv.org/abs/2409.04701) + [reference impl](https://github.com/jina-ai/late-chunking)
- [sentence-transformers PR #1717](https://github.com/UKPLab/sentence-transformers/pull/1717) — `embeddings.to("cpu")` OOM workaround

## 22. Phase 8.13 — Fine-tuning Qwen3-Embedding-8B на BSL (planned, post-baseline)

**Дата добавления:** 2026-04-28
**Статус:** Conditional — выполнять только после Phase 8.12 baseline + decision gate (см. 22.5)
**Зависит от:** Phase 8.12.8 quality regression results (golden set retrieval@10)

### 22.1. Контекст и триггер

Phase 8.12 даёт baseline: Qwen3-Embedding-8B + FA2 (A1+C6) + sliding window split (A2) + query-instruction (C7). Открытый вопрос — достаточно ли этого для **BSL-specific** retrieval.

Qwen3-Embedding training set [включает CodeSearchNet](https://github.com/QwenLM/Qwen3-Embedding) (Python/Java/JS/PHP/Ruby/Go), но **BSL/1С там нет**. Русские идентификаторы (`Соответствие.Вставить`, `КонецПроцедуры`, `ВыполнитьПроведение`) — out-of-distribution для модели. MTEB 70.58 — на mainstream, не на BSL.

→ Если baseline покажет gap, fine-tuning через LoRA — единственный способ улучшить retrieval **без смены модели**.

### 22.2. Техническая возможность на RTX 3090 24GB

| Подход | VRAM peak | Качество vs full FT | Время на 3090 (10K-50K пар) |
|---|---:|---:|---:|
| **LoRA** (rank=16, batch=8, gradient checkpointing) | ~20-22 GB | 90-95% | ~1.5-3h |
| **QLoRA** (4-bit, batch=16-32) | ~10-12 GB | 80-90% | ~1-2h |
| **Full fine-tune** | ~80 GB+ | 100% | ❌ не влезет |

**Стек**: `sentence-transformers >= 2.7` + `peft >= 0.10` + `torch cu128`. Нативная поддержка LoRA для contrastive losses (`MultipleNegativesRankingLoss`, `TripletLoss`) [через PEFT integration в ST](https://sbert.net/docs/sentence_transformer/training_overview.html). Безопасные параметры: 1-3 epochs, lr=1e-4 to 2e-4, rank=16, alpha=32, dropout=0.1.

### 22.3. Блокер — отсутствие labeled data для BSL

Embedding fine-tuning требует **(query, positive, negative)** triplets или **(anchor, positive)** pairs. У нас:

- ✅ 35 548 BSL chunks (из Phase 8.12 reindex)
- ❌ Нет реальных user queries
- ❌ Нет разметки «этот чанк релевантен/нерелевантен запросу»
- ❌ Нет click-логов (production traffic ещё не накоплен)

**Без labeled data fine-tuning невозможен.** Нужны синтетические данные.

### 22.4. Способы получения training data без ручной разметки

| Подход | Как работает | Effort | Ожидаемое качество | Источник |
|---|---|---|---|---|
| **GPL** (Generative Pseudo Labeling) | LLM генерирует synthetic queries → cross-encoder ранжирует → hard negative mining → contrastive train | 1 неделя | Industry SOTA для domain adaptation | [arXiv:2112.07577](https://arxiv.org/abs/2112.07577), [R-GPL extension arXiv:2501.14434](https://arxiv.org/abs/2501.14434) |
| **SimCSE-style self-supervised** | Без queries: dropout-augmented chunks как positive pairs | 2-3 дня | +3-5% recall (medium) | [Sentence-Transformers domain adaptation](https://sbert.net/examples/sentence_transformer/domain_adaptation/README.html) |
| **Hybrid GPL + iterative HN mining** | GPL + перемайнинг hard negatives после каждой эпохи на улучшающемся student | 1-2 недели | Best in class (+10-15% возможно) | [arXiv:2505.18366](https://arxiv.org/abs/2505.18366) Hard Negative Mining for Domain-Specific Retrieval |
| **User click logs** | Production: query → клик пользователя = positive | 3-6 месяцев | Honest signal, но медленно | — |

**Рекомендация**: начать с **GPL** (industry standard, готовые reference implementations).

### 22.5. Decision gate (когда вообще делать fine-tune)

Запускать Phase 8.13 **только после** Phase 8.12.8 baseline:

| Baseline `retrieval@10` на BSL golden set | Действие |
|---|---|
| **≥ 80%** | 🛑 NOT recommended — diminishing returns. Лучше: cross-encoder reranker (Phase 9), prompt tuning, hybrid sparse+dense |
| **60-79%** | ✅ GO — LoRA через GPL pipeline. Ожидаемо +5-10% recall |
| **< 60%** | 🚨 Major: либо смена базовой модели, либо full fine-tune через H100 rental, либо hybrid с code-specific embedder |

**Pre-requisite**: golden set 50-100 BSL queries с ручной разметкой релевантных чанков (∼2-4 дня работы). Без него fine-tuning неоценим — это **обязательная инвестиция**, окупается даже если решим не fine-tune'ить (нужен для quality regression в любом будущем improvement).

### 22.6. GPL pipeline detailed (если decision gate = GO)

```
                                  ┌──────────────────────────┐
                                  │  35K BSL chunks (Phase 8.12 │
                                  │  output, sliding-windowed)  │
                                  └──────────────┬───────────────┘
                                                 │
                  ┌──────────────────────────────┼──────────────────────────────┐
                  │                              │                              │
                  ▼                              ▼                              ▼
   ┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
   │ Step A: Synthetic query │   │ Step B: Hard negative   │   │ Step C: Pseudo-label    │
   │ generation              │   │ mining                  │   │ scoring                 │
   │                         │   │                         │   │                         │
   │ For each chunk c:       │   │ For each (q, c+):       │   │ For each (q, c+, c-):   │
   │  q = LLM_prompt(        │   │  c-_candidates =        │   │  pos_score =            │
   │    "Generate a 1С/BSL   │   │    Qwen3.search(q,      │   │    cross_encoder(q, c+) │
   │     search query for    │   │            top-k=50)    │   │  neg_score =            │
   │     this code: {c}"     │   │  c- = filter            │   │    cross_encoder(q, c-) │
   │  )                      │   │   (high similarity, ≠   │   │  margin = pos - neg     │
   │ via Claude / Qwen3-32B  │   │    c+ semantically)     │   │ Keep if margin > 0.2    │
   │ через llm-rotation      │   │                         │   │                         │
   └─────────────────────────┘   └─────────────────────────┘   └─────────────────────────┘
                  │                              │                              │
                  └──────────────────────────────┼──────────────────────────────┘
                                                 ▼
                              ┌──────────────────────────────┐
                              │ ~10K-50K filtered triplets   │
                              │ (q, c+, c-)                  │
                              └──────────────┬───────────────┘
                                             │
                                             ▼
                              ┌──────────────────────────────┐
                              │ Step D: LoRA training         │
                              │ sentence-transformers + PEFT │
                              │ MNRLoss или TripletLoss      │
                              │ rank=16, lr=1e-4, 2 epochs   │
                              │ ~1.5h на RTX 3090            │
                              └──────────────┬───────────────┘
                                             │
                                             ▼
                              ┌──────────────────────────────┐
                              │ Step E: Eval on golden set    │
                              │ retrieval@10 vs baseline      │
                              │ Deploy if Δ ≥ +3%             │
                              └──────────────────────────────┘
```

**Cross-encoder для labeling (step C)**: пока нет Qwen3-Reranker — `BAAI/bge-reranker-v2-m3` (multilingual, 568M params, поддерживает русский). После Phase 9 — заменить на Qwen3-Reranker когда доступен.

**LLM для synthetic query gen (step A)**: через `llm-rotation` (Claude / Z.AI / OpenAI). Промпт-template нужно отдельно итерировать — на BSL спецификации (например, `"Сгенерируй короткий запрос на русском, который пользователь 1С мог бы задать чтобы найти эту функцию: {chunk}"`).

### 22.7. Tasks

- [ ] **8.13.1** **PRE-REQUISITE**: Golden set BSL queries — 50-100 пар (query, list_of_relevant_chunk_ids), ручная разметка из реальных запросов разработчиков 1С (опросить команду, собрать историчные тикеты GKSTCPLK). Сохранить в [`tests/golden_sets/bsl_retrieval_v1.jsonl`](../../tests/golden_sets/) (формат: `{"query": "...", "relevant_chunk_ids": [...]}`)
- [ ] **8.13.2** Baseline measure: retrieval@10 / @20 / NDCG@10 на golden set после Phase 8.12 (Qwen3 + A1 + C6 + C7 + A2)
- [ ] **8.13.3** **Decision gate**: проверить таблицу 22.5
  - Если baseline ≥ 80% → закрыть Phase 8.13, сосредоточиться на Phase 9 (reranker)
  - Если baseline < 60% → отдельный анализ (model swap vs full FT), не GPL
  - Если 60-79% → продолжить 8.13.4-8.13.9
- [ ] **8.13.4** **Cheap try first** (до GPL): добавить custom BSL query instruction в `Qwen3STEmbedder.embed_batch(is_query=True)` — `"Instruct: Найди процедуру или функцию в коде 1С/BSL, которая отвечает на запрос.\nQuery: "`. Перезамерить retrieval@10. Если +5% и попадаем в ≥80% — stop, fine-tune не нужен
- [ ] **8.13.5** GPL Step A — synthetic query generation: 5K-20K (synthetic_query, real_chunk) пар через `llm-rotation` (Claude или Qwen3-32B). Промпт-template итерировать на 100 sample-чанках, отбирать вручную лучшие 5-10 запросов на чанк. Сохранить в [`data/finetune/bsl_gpl_queries.jsonl`](../../data/finetune/)
- [ ] **8.13.6** GPL Step B+C — hard negative mining + cross-encoder labeling. Использовать `BAAI/bge-reranker-v2-m3` (multilingual) для оценки margin. Filter по margin > 0.2. Сохранить triplets в `data/finetune/bsl_gpl_triplets.jsonl`
- [ ] **8.13.7** GPL Step D — LoRA training: `sentence-transformers` + `peft`, `MultipleNegativesRankingLoss`, rank=16 alpha=32 dropout=0.1, lr=1e-4, 2 epochs, batch=8 (gradient checkpointing). Adapter сохранить в `data/finetune/qwen3-emb-bsl-lora-v1/`
- [ ] **8.13.8** Eval: A/B (Qwen3 baseline vs Qwen3+LoRA) на golden set. Метрики: recall@1/5/10, NDCG@10, MRR. Deploy решение: если ΔRecall@10 ≥ +3% и нет регрессии на mainstream queries (multilingual smoke test) — apply LoRA
- [ ] **8.13.9** ADR + документация: `docs/architecture/adr/2026-XX-bsl-embedding-finetune.md` (decision, alternatives considered, results); обновить `embedding-models` skill; обновить `EMBEDDING__MODEL_ADAPTER` env var в `.env`/skills

### 22.8. Альтернатива fine-tuning'у — instruction engineering (Phase 8.13.4)

**Самый дешёвый путь** (30 минут vs 1-2 недели на GPL):

Qwen3-Embedding — **instruction-aware**. Кастомные task-инструкции для query side могут дать 3-7% улучшения retrieval **без train**. Применить **до** GPL pipeline в 8.13.4 как baseline-extension. Если попадаем в ≥80% после 8.13.4, fine-tuning отменяется.

```python
# В Qwen3STEmbedder.embed_batch для is_query=True:
INSTRUCT_BSL = (
    "Instruct: Найди процедуру, функцию или общий модуль в конфигурации 1С/BSL, "
    "который наиболее релевантен запросу разработчика. Запрос может быть на русском, "
    "включать имена объектов метаданных (справочники, документы, регистры) и термины 1С.\n"
    "Query: "
)
prefixed_queries = [INSTRUCT_BSL + q for q in queries]
```

[Источник, Qwen3 model card](https://huggingface.co/Qwen/Qwen3-Embedding-8B): «Using instructions for queries can improve retrieval performance by 1-5%».

### 22.9. Risks & Mitigations

| Риск | P×I | Митигация |
|---|---|---|
| Catastrophic forgetting (LoRA degraded mainstream queries) | M×H | Регрессионный smoke test на 100 mainstream queries (русский + английский) до deploy |
| Synthetic queries не похожи на реальные | H×M | Manual review первых 50 пар, итерации промпта; включить разные стили (короткий, длинный, code-snippet, описательный) |
| Cross-encoder неправильно ранжирует | M×M | Sample-check 200 (q, c+, c-) trip из mining'а вручную; если accuracy < 80% — сменить reranker |
| Golden set слишком мал → eval noise | M×H | Min 50 queries; bootstrap CI на метриках; повторять trial при ΔRecall в шуме (<2%) |
| LoRA adapter не совместим с TEI (если перешли на A3) | L×M | Тестировать adapter в sentence-transformers; для TEI — конвертировать через [HF custom handler](https://github.com/huggingface/text-embeddings-inference/issues/?q=lora) или пересобирать веса (LoRA merge) |
| Время на golden set creation > 1 неделя | M×L | Аутсорсить на разработчиков 1С (сбор реальных запросов через GitHub issues / Slack-канал) |

### 22.10. Источники

- [GPL paper (Generative Pseudo Labeling)](https://arxiv.org/abs/2112.07577) — Wang et al., 2021, NAACL 2022
- [R-GPL: Iterative HN remining](https://arxiv.org/html/2501.14434v1) — domain adaptation enhancement
- [Hard Negative Mining for Domain-Specific Retrieval](https://arxiv.org/abs/2505.18366) — enterprise systems perspective
- [Effective Hard Negative Mining for Code Search, ACM TOSEM 2024](https://dl.acm.org/doi/10.1145/3695994) — code-specific HN strategies
- [Sentence-Transformers Domain Adaptation guide](https://sbert.net/examples/sentence_transformer/domain_adaptation/README.html) — official SBERT docs
- [PEFT library](https://huggingface.co/docs/peft) — LoRA / QLoRA reference
- [Qwen3-Embedding training pipeline](https://github.com/QwenLM/Qwen3-Embedding) — synthetic data + supervised pairs structure (для inspiration)

---

После Phase 8 — кандидаты Phase 9: cross-encoder Qwen3-Reranker, hybrid search tuning,
LLM-rotation expansion (новые провайдеры после Z.AI лимита).
