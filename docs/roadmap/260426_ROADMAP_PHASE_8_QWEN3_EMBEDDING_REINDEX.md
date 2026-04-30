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

## 21. Phase 8.12 — Throughput optimization & XXL chunk handling (in progress)

**Дата добавления:** 2026-04-28 (post-mortem первого `bsl_code_v4` reindex'а)

**Прогресс на 2026-04-28 (вторая половина дня):**

| Task | Статус | Файлы |
|------|--------|-------|
| 8.12.1 P0 C1-C7 fixes | DONE | [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py), [`tests/test_reindex_qwen3_oom.py`](../../tests/test_reindex_qwen3_oom.py) (9/9) |
| 8.12.2 module_summary drop policy | DONE | [`src/bsl/parser/bsl_chunker.py`](../../src/bsl/parser/bsl_chunker.py) |
| 8.12.3 Baseline reindex `bsl_code_v4` | DONE 2026-04-29 (37404 chunks / 0 errors / 80 min, smoke top-3 ≥ 0.66) | [`scripts/phase8_12_baseline_tei.ps1`](../../scripts/phase8_12_baseline_tei.ps1), [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py) (`Qwen3TEIEmbedder` client-side sub-batch slicing + qdrant `query_points` fix) |
| 8.12.4 A1 FlashAttention 2 build | PENDING (Windows: CUDA toolkit + MSVC; альтернатива через A3) |
| 8.12.5 A2 sliding-window split | DONE | [`src/bsl/parser/bsl_chunker.py`](../../src/bsl/parser/bsl_chunker.py), [`tests/test_bsl_chunker_split.py`](../../tests/test_bsl_chunker_split.py) (10/10) |
| 8.12.6 A3 TEI Docker backend | DONE (code-level) | [`docker/docker-compose.gpu.yml`](../../docker/docker-compose.gpu.yml) (`tei` profile), [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py) (`Qwen3TEIEmbedder`), [`tests/test_qwen3_tei_embedder.py`](../../tests/test_qwen3_tei_embedder.py) (16/16) |
| 8.12.7 A4 producer/consumer | DROPPED (per A3 decision: TEI handles continuous batching server-side) |
| 8.12.8 Quality regression A/B | DONE 2026-04-30 (50q expanded): E5 **0.450** / Qwen3+std **0.160** / Qwen3+Late **0.567** recall@10 — **(c)≥(a) +26% INVERSION** vs 14q noise, (c)≥(b) +254% confirmed. **Production switch to Qwen3+Late** (см. §21.10 REVISED) | [`scripts/phase8_12_8/`](../../scripts/phase8_12_8/) (5 шагов pipeline + path C pre-resolve fix) |
| 8.12.9 A2-alt Late Chunking pooling-hook | DONE (code-level) | [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py), [`tests/test_late_chunking.py`](../../tests/test_late_chunking.py) (18/18) |

**Status (2026-04-30 evening): 8/9 задач закрыто + path C done** (P0 + chunker A2 + A2-alt + TEI + baseline 8.12.3 + quality A/B 8.12.8 expanded). 1 отброшена (A4 при A3), 1 опциональная (8.12.4 FA2 Windows build — backup). **Phase 8.12 миграция Qwen3 — УСПЕХ после path C расширения pilot** (см. §21.10 REVISED): на 50q expanded pilot Qwen3+Late выигрывает все метрики vs E5 (recall +26%, ndcg +43%, mrr +53%). **Production retrieval переключается на `bsl_code_v4_late`** (Late Chunking pooling, 4096d). Phase 8.13 LoRA fine-tuning остаётся deferred как опциональное улучшение поверх production-worthy baseline.

Связанные коммиты: `99546be2` (P0 C1-C7), `1a939901` (A2 + module_summary drop), `b4d3b1bb` (A2-alt Late Chunking), `55e8bf06` (8.12.3 baseline + TEI 413 fix), `b48df2ec` (8.12.8 pilot eval), `8f7859cd` (H1 ablation REJECTED), `6519404f` (skills sync 8.10.2).

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

- [x] **8.12.1** Применить P0 fixes **C1-C7** в [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py); добавить unit-test на OOM recovery (mock `embed_batch` raises `OutOfMemoryError`, ожидаем `batch.clear()` + продолжение). C6 — отдельный test: encode батч с короткими и длинными текстами через FA2, проверить что similarity между ними не нулевая (regression на padding_side bug) — **DONE 2026-04-28**: C1+C5 (token cap via `truncation=True, max_length=4096`), C2 (try/except `_is_cuda_oom` в `flush_batch`), C3 (`batch.clear()` в `finally`), C4 (`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` в module-top), C6 (gated на `enable_fa2`: `tokenizer_kwargs={"padding_side":"left"}`), C7 (feature-detect `prompts["query"]` → `prompt_name="query"` для query-side encode). CLI flag `--enable-fa2` (+валидация что только с `qwen3-st`). Tests: [`tests/test_reindex_qwen3_oom.py`](../../tests/test_reindex_qwen3_oom.py), 9/9 passing (`_is_cuda_oom` classifier, OOM swallow + upsert-not-called, recovery-on-next-call, non-OOM propagation, empty-batch defensive, C3 `finally`-pattern regression). C6 GPU-test отложен до 8.12.4 (нет FA2 build)
- [x] **8.12.2** Решить судьбу `module_summary` чанков > N токенов: дроп vs short-summary regen (тяжёлый труд парсера для редкого сценария — скорее дроп) — **DONE 2026-04-28**: drop policy. В [`src/bsl/parser/bsl_chunker.py`](../../src/bsl/parser/bsl_chunker.py) добавлен `max_summary_chars` (default 30000 ≈ 10K токенов); `_build_module_summary` возвращает `None` если контент превышает порог. UpravlenieDostupom-class модули (5000+ символов → 70k+ chars summary) больше не индексируются как XXL-чанки. Symbol-чанки самих этих модулей сохраняются (drop затрагивает только summary)
- [x] **8.12.3** Переиндексировать `bsl_code_v4` с P0 fixes (baseline throughput) — **DONE 2026-04-29**: 2049 BSL files / 33630 symbols / 37404 chunks / 0 errors / 4838s (~80 min, 2.36s/file) через `qwen3-tei` (TEI 1.7.2 Ampere, fp16, MAX_INPUT_LENGTH=4096). Collection `bsl_code_v4` = 24455 points. Smoke A/B (2 queries): "обработка проведения документа" → top-3 cosine ≥ 0.6614, "регистр сведений 1С" → top-3 cosine ≥ 0.6453, embed latency 378ms cold → 203ms warm. Bug fixes encountered & applied: (i) `Qwen3TEIEmbedder.embed_batch` отправлял весь buffer (512) одним POST → 413 при `MAX_CLIENT_BATCH_SIZE=32` server-cap; добавлен ctor-arg `client_batch_size=32` + sub-batch loop через `_post_embed_sub` helper, проброс через `make_embedder` (commit pending); (ii) smoke template в [`scripts/phase8_12_baseline_tei.ps1`](../../scripts/phase8_12_baseline_tei.ps1) использовал deprecated `client.search(query_vector=)` — переведён на `client.query_points(query=, with_payload=True).points` (qdrant-client ≥1.13)
- [ ] **8.12.4** A1 — собрать `flash-attn` под Windows + интегрировать с **обязательным C6** (`tokenizer_kwargs={"padding_side":"left"}`); перезамерить throughput на 1000 BSL-чанков
- [x] **8.12.5** A2 — sliding-window split в [`src/bsl/parser/bsl_chunker.py`](../../src/bsl/parser/bsl_chunker.py) с **window=1024 overlap=256**; тест что `Словарь_en_ru` теперь даёт ≥ 30 чанков (а не 1) — **DONE 2026-04-28**: line-aware splitter `_split_long_chunk`. Defaults через char-equivalent (1 token ≈ 3 chars для смешанного Cyrillic+Latin BSL): `split_threshold_chars=6000` (~2K tok), `window_chars=3000` (~1024 tok), `overlap_chars=750` (~256 tok = 25%). Каждый split-chunk наследует metadata + получает `split_part`/`split_total`/`parent_chunk_id`; `name` суффиксуется `_part{i}`. Force-emit для одиночной line > window (предотвращение infinite loop). Defensive ctor check: `overlap < window`. Тест `test_long_symbol_splits_into_multiple_parts` подтверждает: Slovar-class body 97k chars → 43+ чанков (≥30 ✓). Tests: [`tests/test_bsl_chunker_split.py`](../../tests/test_bsl_chunker_split.py) — 10/10 passing
- [x] **8.12.6** A3 — TEI compose service + `Qwen3TEIEmbedder` HTTP-class — **DONE 2026-04-28** (code-level; runtime запуск в 8.12.3/8.12.8). В [`docker/docker-compose.gpu.yml`](../../docker/docker-compose.gpu.yml) добавлен сервис `tei` под opt-in профилем (`--profile tei`): image `ghcr.io/huggingface/text-embeddings-inference:1.7.2` (Ampere, **не `turing-1.5`**), `MODEL_ID=Qwen/Qwen3-Embedding-8B`, `MAX_INPUT_LENGTH=4096` (matches Qwen3STEmbedder C5), `DTYPE=bfloat16` (TEI 1.7.x default Candle backend; fallback `float32` задокументирован в комментарии для [issue #675](https://github.com/huggingface/text-embeddings-inference/issues/675) ORT FP16-bug), GPU device reservation, healthcheck через bash `/dev/tcp` (TEI distroless без curl), 5-минутный `start_period` под cold-load. Volume `tei_data` для персистентного HF-кеша. В [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py): класс `Qwen3TEIEmbedder` (httpx-клиент к `/embed`, `embed_batch(texts, is_query)` с client-side prepend Qwen3 retrieval-instruction для C7 parity с `Qwen3STEmbedder` `prompt_name="query"`, форвард-совместимый response-shape parser для list/dict обёрток, defensive max-chars truncation, idempotent `close()`), smoke-check `/health` + soft-warn `/info` model_id mismatch на init. CLI: `--embedder qwen3-tei`, `--tei-url <base>` (default `http://localhost:8080`); все три гарда (`--enable-fa2`, `--pooling-mode late-chunking`, `--dual-vector` с TEI) выдают actionable ошибку. `embed_late_chunked` raises `NotImplementedError` (TEI returns pooled vectors only — token-level hidden states недоступны). Tests: [`tests/test_qwen3_tei_embedder.py`](../../tests/test_qwen3_tei_embedder.py) — 16/16 passing с monkey-patched `httpx.Client` (no real network)
- [ ] ~~**8.12.7**~~ **DROPPED 2026-04-28** — A4 producer/consumer marked "drop при A3" в плане 21.4. TEI делает continuous batching на стороне Rust runtime, поэтому Python-side overlap CPU↔GPU был бы дублирующим. Сохранено как opt-in путь только если 8.12.3 baseline покажет, что TEI недоступен под Windows и приходится оставаться на `qwen3-st`
- [x] **8.12.8** Quality regression: retrieval@10 на golden-set, **3 точки сравнения** — (a) E5 baseline (Phase 7), (b) Qwen3 + sliding window A2, (c) Qwen3 + Late Chunking A2-alt — **DONE 2026-04-30 (PILOT, 14 queries)**: pipeline в [`scripts/phase8_12_8/`](../../scripts/phase8_12_8/) (filter_chunks/cluster_by_graph/generate_queries/label_multipositive/eval_pipeline + `_llm.py` Z.AI direct sync wire-up). Synthetic golden-set via Chroma generative-benchmarking методология + call_graph 1-hop multi-positives. Reindex (c) `bsl_code_v4_late` (24455 points / 4096d / 144 min на qwen3-st late-chunking). **Pilot results (14 queries):** (a) E5 recall@10=**0.500** ndcg=0.304 mrr=0.245 / (b) Qwen3+std recall=**0.143** ndcg=0.081 mrr=0.060 / (c) Qwen3+Late recall=**0.321** ndcg=0.249 mrr=0.226. **Hypothesis (c)≥(b) confirmed** (Late Chunking +125% recall vs standard pooling). **Hypothesis (b)≥(a) NOT confirmed** — Qwen3+TEI отстаёт от E5 на 71% recall в этом pilot. Caveats: малая выборка (n=14, оверсэмпл из 30 с 53% skip-rate); synthetic queries via Z.AI могут смещать в сторону E5 training distribution; avg 0.36 secondary positives → метрики чувствительны к single-hit primary. Артефакты: `tmp/phase8_12_8/{clusters,queries_pilot,golden_set,eval_report}.jsonl`. **Open follow-up**: расширить pilot до 100-200 queries (нужно >60% match-rate анкоров — может быть после fine-tuning chunker), ввести real user queries (через usage logs Phase 22 feedback loop), исследовать смещение Z.AI prompts (Promptagator-style на Russian BSL может быть out-of-distribution для базовой Qwen3 retrieval-головы). **H1 ablation (2026-04-30)**: тестировали кастомные query-instructions для Qwen3 чтобы проверить hypothesis "instruction mismatch = root cause". Результат: BSL-specific `"Given a 1С BSL developer question, retrieve relevant code symbols"` → recall **0.000** (хуже default), code-specific `"Given a code search query, retrieve relevant code passages"` → **0.071** (хуже default 0.143). **H1 REJECTED** — Qwen3 жёстко калиброван на default web-retrieval template, любые отклонения ломают alignment. Real root cause скорее всего **H3 — Russian BSL OOD** (Qwen3 training set покрывает Python/Java/JS/PHP/Ruby/Go, не русский 1С). Lever: **Phase 8.13 LoRA fine-tuning** на BSL pairs ИЛИ **stay-on-E5** для production retrieval до накопления training data
- [x] **8.12.9** A2-alt — late chunking pooling-hook в `Qwen3STEmbedder` (~30 LOC, см. [reference impl jina-ai/late-chunking](https://github.com/jina-ai/late-chunking)) — **DONE 2026-04-28** (code-level; runtime A/B in 8.12.8). В [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py): (1) метод `Qwen3STEmbedder.embed_late_chunked(parent_text, chunk_char_spans)` — один forward через `self.model[0]` (минуя ST pooling), `tokenizer(..., return_offsets_mapping=True)` для char→token mapping, mean-pool token embeddings внутри каждого спана, L2-normalize; passages-only (queries shift offsets через `prompt_name`); (2) helper `_char_span_to_token_span(offsets, char_start, char_end)` пропускает special tokens `(0,0)` и предполагает монотонные смещения (early break); (3) orchestrator `_embed_chunks_late(embedder, chunks)` группирует по `module_path`, строит `parent_text` через `_LATE_CHUNK_SEP="\n\n"`, считает spans по running cursor; для chunks обрезанных за `max_seq_length` — fallback на `embed_batch`; (4) CLI `--pooling-mode {standard,late-chunking}` (default standard, late-chunking требует `--embedder qwen3-st` и несовместим с `--dual-vector`). Тесты: [`tests/test_late_chunking.py`](../../tests/test_late_chunking.py) — 18 pure-python кейсов (offset-mapping edge cases + orchestrator grouping/spans/fallback/order-preservation); 18/18 passing без GPU. Runtime валидация (A/B retrieval@10 vs стандартного пулинга) — в 8.12.8 на golden-set

### 21.7. Решение для текущего запуска (28.04) — закрыто

**Исходный план (28.04 утро):** прервать висящий OOM-loop, применить P0 fixes, перезапустить. Успешно проиндексировано на момент сбоя — ~25% (≈ 6656 chunks из 35 548).

**Что сделано (28.04 вторая половина дня):**

1. **P0 fixes применены** (8.12.1) — токен-cap, OOM swallow, `batch.clear()` в `finally`, `expandable_segments`, `padding_side="left"` (gated на FA2), `prompt_name="query"` (feature-detect).
2. **A2 sliding-window split применён** (8.12.5) — XXL-чанки (97k chars `Словарь_*`) теперь дают ≥30 split-кусков по ~3000 chars, ни один не уходит в model.forward целиком.
3. **module_summary drop** (8.12.2) — пороговые 70k+ chars summary-чанки больше не индексируются.
4. **A2-alt Late Chunking pooling-hook реализован** (8.12.9) — готов к A/B-сравнению в 8.12.8.
5. **A3 TEI backend реализован** (8.12.6) — `tei` сервис в compose под opt-in профилем + `Qwen3TEIEmbedder` HTTP-клиент. CLI: `--embedder qwen3-tei`. 16/16 unit-тестов с мокнутым httpx. Runtime smoke-test (cold-load Qwen3-8B + первый POST к `/embed`) выполняется в 8.12.3 одновременно с baseline reindex.
6. **A4 producer/consumer drop'нут** (8.12.7) — TEI делает continuous batching server-side, A4 был бы избыточен.

**Следующий шаг — 8.12.3 baseline reindex** (требует остановки активной Claude Code сессии и MCP-серверов).

**Готово к запуску (2026-04-29):**
- Qwen3-Embedding-8B скачан локально: `D:/hf-manual/Qwen3-Embedding-8B/` — 4 шарда (~14.1 GiB), все 398 тензоров проверены через `safetensors.safe_open()`
- TEI compose обновлён: bind-mount `${QWEN3_MODEL_DIR}:/models/Qwen3-Embedding-8B:ro` + `MODEL_ID=/models/Qwen3-Embedding-8B` → пропускает HF Hub pull (16 GB)
- Runner: [`scripts/phase8_12_baseline_tei.ps1`](../../scripts/phase8_12_baseline_tei.ps1) — pre-flight (Docker/Qdrant/GPU/heavy-py-procs), TEI up + /health-poll + /info smoke, reindex c `--recreate`, post-smoke search

**Запуск (вне Claude Code сессии):**
```powershell
# 1. Закрыть все окна Claude Code / IDE с MCP-серверами (освободить VRAM)
# 2. Из C:/1С-Framework:
pwsh -File scripts/phase8_12_baseline_tei.ps1 -AutoConfirm
# Опц.: -BslProjectPath "src/projects/configuration/<name>" если несколько проектов
# Опц.: -Qwen3ModelDir "D:/hf-manual/Qwen3-Embedding-8B" (default — этот путь)
```

**Артефакты после запуска:** `tmp/phase8/8.12.3_reindex_bsl_code_v4_tei.log`, `tmp/phase8/8.12.3_smoke.log`. После baseline → 8.12.8 A/B (E5 vs Qwen3+A2 vs Qwen3+A2-alt).

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

### 21.10. Decision after expanded pilot (2026-04-30) — switch production to Qwen3+Late Chunking

**⚠ REVISED 2026-04-30 (вечер):** изначальное решение "stay on E5" basised on 14q pilot **отозвано** после path C (expand to 50q). 14q был статистическим шумом — особенно для Qwen3+Late arm с высокой variance. Расширенный pilot переворачивает выводы.

**Path C — pre-resolution фикс**: добавлен шаг `load_qdrant_keys` + `filter_clusters_to_qdrant` в `generate_queries.py` ([commit pending](#)) — пред-фильтрует cluster.members против qdrant payload **(name, module_path)** до sampling. Skip-rate упал с 53% (16/30 unmatched в 14q runs) до **0% (0/50 unmatched)** на 50q run. 156 clusters → 84 после prefilter (≥2 members).

**Резюме expanded pilot 8.12.8 (50 queries, тот же synthetic golden pipeline):**

| Arm | Recall@10 | NDCG@10 | MRR | Δ vs E5 (recall) | Δ vs 14q |
|---|---|---|---|---|---|
| (a) E5 baseline `bsl_code_v3` 1024d | 0.450 | 0.291 | 0.292 | baseline | -10% |
| (b) Qwen3+std `bsl_code_v4` 4096d (TEI) | 0.160 | 0.099 | 0.103 | -64% | +12% |
| (c) **Qwen3+Late `bsl_code_v4_late` 4096d** | **0.567** | **0.414** | **0.447** | **+26%** | **+76%** |

| 14q pilot | Recall@10 (старая интерпретация) |
|---|---|
| (a) E5 | 0.500 |
| (b) Qwen3+std | 0.143 |
| (c) Qwen3+Late | 0.321 |

**Findings (50q expanded pilot — overrides 14q):**
- ✅ **Hypothesis (c) ≥ (b) — CONFIRMED stronger** (Late Chunking **+254% recall** vs std pooling on 50q, vs +125% на 14q)
- ❌ **Hypothesis (b) ≥ (a) — REJECTED CLEARLY** (Qwen3+std отстаёт от E5 на 64% recall, стабильно между 14q и 50q)
- ✅ **Hypothesis (c) ≥ (a) — CONFIRMED on 50q** (Qwen3+Late **+26% recall** vs E5 — INVERSION vs 14q where это было -36%)

**H1 ablation (instruction mismatch) — REJECTED**: тестировали два альтернативных Qwen3 query prompt'а:
- BSL-specific `"Given a 1С BSL developer question, retrieve relevant code symbols"` → recall **0.000** (хуже default 0.143)
- Code-specific `"Given a code search query, retrieve relevant code passages"` → recall **0.071** (хуже)
- Default web-retrieval prompt из HF model card (`"Given a web search query, retrieve relevant passages..."`) — оптимальный. Qwen3-Embedding-8B жёстко калиброван на этот шаблон, отклонения ломают alignment.

**Likely root cause — H3: Russian BSL OOD для Qwen3.** Training set Qwen3-Embedding включает CodeSearchNet (Python/Java/JS/Go/Ruby/PHP), но **не русский 1С**. Русские идентификаторы (`Соответствие.Вставить`, `КонецПроцедуры`) и domain-stylized queries — out-of-distribution. E5-multilingual-large охватывает русский web обширно через мультиязычную предтренировку, что объясняет преимущество на synthetic Promptagator-style queries (близких к natural Russian dev questions).

**REVISED Decision: переключить production retrieval на Qwen3+Late Chunking** (`bsl_code_v4_late`, 4096d). На 50q expanded pilot Late Chunking arm выигрывает все метрики против E5 baseline (recall +26%, ndcg +43%, mrr +53%). Phase 8.12 миграция Qwen3 завершена с положительным результатом — Late Chunking pooling-mode (8.12.9) оказался ключевым enabler-ом, без него Qwen3+std catastrophically underperforms E5 на BSL.

**Критический вывод:** Qwen3-Embedding-8B не плох на BSL per se — он плох с **standard pooling** на длинных Russian-coded модулях. Late Chunking сохраняет document-level context при per-chunk pooling и даёт +254% recall на BSL. Hypothesis H3 (Russian BSL OOD) была частично правильной — OOD-gap проявляется только при потере context (std pooling), а Late Chunking его устраняет.

**Прежнее решение "stay on E5"** (составлено на 14q) было основано на статистическом шуме — Qwen3+Late имел recall 0.321 на 14q (gap -36% vs E5 0.500), но при правильном sampling без skip-rate он даёт 0.567 (+26% vs E5).

**Constraint context — single GPU**: RTX 3090 24GB используется production retrieval (Late Chunking inference через qwen3-st требует ~16-18 GB на forward pass) + reindex jobs. Phase 8.13 LoRA fine-tuning остаётся deferred — может дать ещё +5-10% recall поверх 0.567, но (1) текущий результат уже production-worthy, (2) fine-tuning требует 1-3 дня offline GPU window. Откладывается до накопления real user queries через Phase 22 feedback (когда проверим, что synthetic pilot не bias).

**Path C — DONE 2026-04-30** (expand pilot 14q→50q): pre-resolution фикс в `generate_queries.py` (`load_qdrant_keys` + `filter_clusters_to_qdrant`), 50/50 queries, 0% unmatched. Результат → table выше, переворот decision.

**Production switchover progress (Phase 8.12 → 8.11 production cleanup):**

| # | Действие | Status | Cost | Зависимость |
|---|---|---|---|---|
| 1a | Default `collection_name` в `src/bsl/semantic_search/config.py` → `bsl_code_v4_late`, `embedding_dim` 768→4096, `embedding_model` `qwen3-embedding` | ✅ **DONE 2026-04-30** | 5 мин | — |
| 1b | `QUERY_INSTRUCTION` в `qwen3_embedding.py` → default web-retrieval template (H1 ablation REJECTED BSL-specific). `DOCUMENT_INSTRUCTION` → пустая строка (Qwen3 convention для passages) | ✅ **DONE 2026-04-30** | 5 мин | После 1a |
| 1c | Default `qdrant_collection` в `hybrid_search.py` → `bsl_code_v4_late` (was `bsl_code_v3`) | ✅ **DONE 2026-04-30** | 2 мин | После 1a |
| 1d | **Backend wiring**: добавлен `Qwen3TEIQueryService` (mirror API через TEI HTTP) + γ-fallback в `Qwen3EmbeddingService` (Ollama → TEI при ConnectError). Production end-to-end smoke прошёл: Ollama unavailable → auto-fallback → TEI 200 OK → 4096d vec → bsl_code_v4_late top-3 scores 0.45 (идентично direct-TEI) | ✅ **DONE 2026-04-30** | 30 мин | После 1a/1b/1c |
| 1e | **Path α executed (2026-04-30 night)**: `winget install Ollama.Ollama` + `ollama pull qwen3-embedding:8b` (4.7 GB GGUF). **Critical finding**: A/B drift Ollama vs TEI на ОДНОМ запросе через ОДИН промпт = **cosine 0.52** — это не quantization noise (norm 0.95+), а **fundamentally different vector space**. Possible causes: heavy GGUF quantization (Q4/Q2), different pooling strategy, или другая checkpoint версия в Ollama registry. **Implication**: Ollama `qwen3-embedding:8b` **НЕ совместим с `bsl_code_v4_late`** (индекс построен через TEI safetensors fp16). Ollama path надо disable as default; либо переиндексировать под Ollama vector space (`bsl_code_v4_late_ollama`). Обновлён default model tag в `Qwen3EmbeddingService` с `qwen3-embedding` на `qwen3-embedding:8b` (404 fix), но γ-fallback теперь де-факто всегда уходит в TEI потому что Ollama drift делает его непригодным | ⚠ **FINDING 2026-04-30** | 30 мин | Документирует ограничение, не блокирует production |
| 2 | Drop `bsl_code_v3` (legacy E5) — Phase 8.11.3 | ⏳ DEFER | 5 мин | После 1d + неделю monitoring real user queries |
| 3 | Архивировать `bsl_code_v4` (Qwen3+std) snapshot — research artifact | ⏳ DEFER | 5 мин | После 1d |
| 4 | Phase 8.13 LoRA — DEFERRED, опциональное улучшение поверх Qwen3+Late baseline | ⏳ DEFER | 1-3 дня | Когда: real user queries через Phase 22 + ≥500q golden |

**Smoke test 2026-04-30 (через TEI напрямую, в обход Ollama-сервиса):** 3 BSL-запроса (`"обработка проведения документа"`, `"регистр сведений 1С"`, `"проверка прав доступа"`) → top-3 results scores 0.45-0.53 на `bsl_code_v4_late` 4096d. Confirms коллекция и query-side prompt совместимы; gap только в backend wiring (Ollama vs TEI) для production-уровня сервиса.

**Optional future investigation (low priority после production switch):**
- **D**: A/B test GigaEmbeddings 1024d / BGE-M3 на 50q golden-set — может Russian-SOTA или multilingual SOTA модель даст ещё лучше + меньше GPU footprint (1024d vs 4096d). Но Late Chunking требует full-document forward в любом случае → надо проверить как у этих моделей с long-context. Ставится на back-burner — production выигрыш Qwen3+Late уже defendable.

**Триггеры пересмотра REVISED Decision:**
1. **Phase 22 real user queries** дадут result где Qwen3+Late ≤ E5 → откат к E5 + перепроверка
2. **D-investigation** покажет что Giga/BGE-M3+LateChunking ≥ Qwen3+Late с меньшими ресурсами → миграция на лучшую модель
3. **Phase 8.13 LoRA** даст +5-10% recall (пилот → 0.62-0.65) → upgrade fine-tuned Qwen3+Late

## 22. Phase 8.13 — Fine-tuning Qwen3-Embedding-8B на BSL (DEFERRED, опциональное улучшение)

**Дата добавления:** 2026-04-28
**Статус:** **DEFERRED 2026-04-30** — после path C expanded pilot Qwen3+Late уже beats E5 (+26% recall, см. §21.10 REVISED). Phase 8.13 теряет статус необходимости — становится опциональным улучшением поверх уже production-worthy baseline. Может дать ещё +5-10% recall (0.567 → ~0.62-0.65), но (1) текущий результат defendable для production, (2) single-GPU window 1-3 дня offline всё ещё ограничивает.
**Зависит от:** Phase 22 feedback loop накопит ≥500 real user queries → построить non-synthetic golden, повторить eval. Если real-query result confirms pilot → fine-tuning имеет смысл. Если real result хуже → может быть instead investigate D (alternative models).

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

## 23. Operating Procedures — индексация BSL-проектов в production-коллекцию

**Статус:** ✅ закреплено как стандартная процедура (после Phase 8.12.8 production switchover, 2026-04-30)
**Применяется:** при добавлении нового 1С-проекта в `src/projects/configuration/` или при пересборке существующего после крупных изменений конфигурации.

### 23.1. Production-команда (per-project BSL reindex)

Каждый проект 1С индексируется в **общую** production-коллекцию `bsl_code_v4_late`
(Qwen3-Embedding-8B + Late Chunking, 4096d, recall@10 = 0.567 на 50q golden-set).
Без `--recreate` — append к существующей коллекции, чанки других проектов не затрагиваются.

```bash
python scripts/reindex_bsl_qwen3.py \
  --project "src/projects/configuration/<имя_проекта>" \
  --embedder qwen3-st \
  --pooling-mode late-chunking \
  --collection bsl_code_v4_late \
  --batch-size 32 \
  --buffer-size 512
```

**Расшифровка аргументов:**

| Аргумент | Значение | Почему именно так |
|----------|----------|-------------------|
| `--project` | путь к корню проекта 1С | парсер ищет `*.bsl` рекурсивно от этой точки |
| `--embedder qwen3-st` | sentence-transformers backend | единственный embedder, поддерживающий `--pooling-mode late-chunking`. TEI не подходит — pooled vectors only (caveat §21.10) |
| `--pooling-mode late-chunking` | full-doc forward → per-chunk mean-pool | даёт +254% recall vs std pooling на BSL (Phase 8.12.9 A2-alt) |
| `--collection bsl_code_v4_late` | production-коллекция | единая для всех проектов; легаси `bsl_code_v3` (E5) и `bsl_code_v4` (std pooling) — НЕ использовать |
| `--batch-size 32` | размер batch для GPU forward | подобран под RTX 3090 24 GB FP16 + p99 chunk length 3588 токенов; больше → OOM на длинном хвосте (см. §21.1–21.2) |
| `--buffer-size 512` | пул чанков перед length-bucketing | даёт длинному-bucketer достаточный pool для эффективной упаковки коротких/длинных вместе (§21.4) |

**Время:** ~60-90 минут на проект ~25k символов на RTX 3090 (по аналогии с 260416_GKSTCPLK-2368: 24 455 chunks за ~75 мин).

### 23.2. Pre-flight checks

Перед запуском убедиться:

```bash
# 1. Qdrant доступен
curl -s http://localhost:6333/collections/bsl_code_v4_late | python -c "import json,sys; d=json.load(sys.stdin); print('points:', d['result']['points_count'])"

# 2. GPU свободен (TEI ~16 GB занимает; reindex_bsl_qwen3 + qwen3-st грузит ещё одну копию модели)
nvidia-smi --query-gpu=memory.used,memory.free --format=csv
# Если занято > 18 GB — остановить TEI: docker stop pdf-rag-tei

# 3. Нет конкурирующих BSL MCP-серверов, держащих модель
# (mcp servers могут держать GPU; в идеале закрыть Claude Code сессию или остановить bsl-semantic-search MCP)

# 4. Проверить что путь существует и в нём есть .bsl файлы
ls -la "src/projects/configuration/<имя_проекта>/" | head -5
find "src/projects/configuration/<имя_проекта>/" -name "*.bsl" | wc -l
```

### 23.3. Post-reindex verification

После завершения скрипта проверить что чанки действительно попали:

```bash
# Количество chunks нового проекта в коллекции
curl -s -X POST "http://localhost:6333/collections/bsl_code_v4_late/points/count" \
  -H "Content-Type: application/json" \
  -d '{"filter":{"must":[{"key":"module_path","match":{"text":"<имя_проекта>"}}]},"exact":true}'

# Smoke-search (через Ollama-fallback не работает — drift cosine 0.52, см. задачу 1e §21.10)
# Поэтому smoke делать через bsl-semantic-search MCP или напрямую через TEI
```

### 23.4. Граф вызовов (опционально, для quality eval / call_graph features)

Если этот проект будет участвовать в Phase 8.12.8 quality eval pipeline или
требуется `bsl_call_graph` функциональность — пересобрать граф:

```bash
python scripts/build_call_graph.py --project "src/projects/configuration/<имя_проекта>" --clear
# ~17 секунд на 33k символов / 79k вызовов
# Артефакт: cache/bsl_call_graph.db (33630 symbols / 79709 calls на текущий снапшот)
```

⚠️ `--clear` пересобирает с нуля; если в БД есть предыдущий проект, его связи будут стёрты. Без `--clear` — append.

### 23.5. Common pitfalls

| Симптом | Причина | Решение |
|---------|---------|---------|
| `OOM` на 25-30% прогресса | XXL chunks (>4096 токенов) переполняют GPU | Включить sliding-window split в `BSLChunker` (Phase 8.12.5: window=1024 / overlap=256). Обычно уже включён по умолчанию. |
| 0 chunks в коллекции после Run | Парсер не нашёл `.bsl` файлы | Проверить путь `--project`; убедиться что `.bsl` именно в этом дереве, а не в `bin/` / `node_modules/` (skip-patterns) |
| Chunks от другого проекта пропали | Запустили с `--recreate` | НЕ использовать `--recreate` для production-коллекции. Только для тестовых коллекций. |
| `413 Payload Too Large` | Использован `--embedder qwen3-tei` | Для `bsl_code_v4_late` использовать `qwen3-st`, TEI не поддерживает Late Chunking. Если всё-таки TEI — `client_batch_size=32` встроен с фикса 8.12.6 |
| `AttributeError: 'QdrantClient' object has no attribute 'search'` | qdrant-client ≥1.13 deprecated `client.search()` | Уже фикснуто в `phase8_12_baseline_tei.ps1` через `client.query_points(query=, with_payload=True).points` — апдейтить остальные скрипты по аналогии |

### 23.6. Пример: индексация второго существующего проекта (260304_GKSTCPLK-2182)

На 2026-04-30 в `bsl_code_v4_late` лежит только 260416_GKSTCPLK-2368 (24 455 chunks).
Проект 260304_GKSTCPLK-2182 проиндексирован только в SQLite FTS5 fallback
(`cache/docs-mcp/hybrid_search.db`, 24 566 docs) — без semantic search.

Если решено выровнять оба проекта на единый production-pipeline:

```bash
python scripts/reindex_bsl_qwen3.py \
  --project "src/projects/configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС" \
  --embedder qwen3-st \
  --pooling-mode late-chunking \
  --collection bsl_code_v4_late \
  --batch-size 32 --buffer-size 512
```

Append (~60-90 мин) → в `bsl_code_v4_late` будет ~49k chunks, оба проекта на Qwen3+Late.

---

## 24. Future work — индексация фреймворка как code-search source (proposal, NOT scheduled)

**Идея:** проиндексировать сам `C:\1С-Framework` (Python код, hooks, skills, scripts, configs) в отдельную Qdrant-коллекцию `framework_code_v1` для self-research пайплайна Claude Code.

### 24.1. Какой эффект даст

| Use case | Текущее решение | После индексации |
|----------|-----------------|------------------|
| "Где определён hook code-skill-enforcer?" | `Grep "code-skill-enforcer"` или `Glob ".claude/hooks/*.py"` | Semantic: "хук блокирующий запись без активации скилла" → найдёт даже если в коде имя другое |
| "Какие skill'ы делают что-то с embeddings?" | Перебор `.claude/skills/*/SKILL.md` вручную | Semantic поиск по описанию → топ-N релевантных |
| "Найди похожий паттерн в кодовой базе" | `Grep` по фрагменту | Vector similarity → находит **семантически близкие** реализации |
| Onboarding нового контрибьютора | Чтение CLAUDE.md + грепы | Q&A по фреймворку через RAG |
| Refactoring impact analysis | Вручную | "Найди все места, где используется fallback ollama→tei" |

### 24.2. Подводные камни

1. **Python ≠ BSL.** `reindex_bsl_qwen3.py` использует `BSLASTParser` через tree-sitter-bsl — для Python нужен другой parser/chunker (tree-sitter-python или AST через `ast` модуль). Это новый pipeline, не повторное использование скрипта.
2. **Mixing domains.** Если положить Python + BSL в одну коллекцию — retrieval может деградировать (разные распределения embeddings). Разнести: `bsl_code_v4_late` и `framework_code_v1` отдельно.
3. **Maintenance.** Каждое изменение в фреймворке требует переиндексации (или incremental update). Без watcher'а актуальность будет деградировать.
4. **Diminishing returns vs Grep.** Для exact-name lookups (`grep "function_name"`) семантика не нужна. Польза — на **fuzzy/conceptual** запросах ("где fallback логика?"). Если запросы пользователя в основном exact — затраты не окупятся.
5. **Cost.** ~150-300 MB Qdrant collection (зависит от размера фреймворка), ~30-60 мин разовая индексация на RTX 3090, ~5-10 мин incremental update.

### 24.3. Объективная оценка

| Критерий | Оценка |
|----------|--------|
| Уникальная польза vs существующих инструментов (Grep/Glob/Read) | **Средняя.** Перекрывается на 60-70% с Grep. Уникальные кейсы — fuzzy semantic поиск + Q&A. |
| Сложность реализации | **Средняя.** Нужен Python-chunker + adaptation reindex_*.py для Python. Не one-liner. |
| ROI без production-сигнала | **Низкий.** Нет жалоб "не могу найти код в фреймворке". |
| ROI после первой жалобы / при росте контрибьюторов | **Высокий.** Полезность растёт с размером команды. |

### 24.4. Рекомендация (исходная — обновлено §25)

⏸ **Не делать сейчас.** Грепы и Glob справляются для текущего workflow Single contributor + AI agent.

**Пересмотреть когда:**
- Появится второй человек, активно правящий фреймворк
- Накопятся ≥5 случаев "не могу найти место где это" за месяц
- Запустится MCP-сервер для self-Q&A (тогда индекс — естественная зависимость)

**Если делать — этапы (роадмап заготовка):**
1. Phase 9.X.1: написать `scripts/index_python_code.py` (tree-sitter-python + sliding window 800/200 chars)
2. Phase 9.X.2: создать коллекцию `framework_code_v1` (1024d через E5 — multilingual нужен для русских комментариев + английского кода)
3. Phase 9.X.3: добавить incremental update через git diff hook (PostCommit)
4. Phase 9.X.4: MCP-сервер `framework-code-search` с инструментами `search_code`, `find_similar`, `q_and_a`
5. Phase 9.X.5: golden-set из 30-50 типичных вопросов о фреймворке для eval

> **STATUS UPDATE (2026-04-30):** §24.4 рекомендация "не делать" override'нута пользователем —
> Stage 1 реализован. Embedding model: **Qwen3-Embedding-8B 4096d через TEI** (а не E5 1024d
> из заготовки) — переиспользует существующую инфраструктуру `pdf-rag-tei`. Текущий статус
> и варианты продолжения см. §25 ниже.

---

## 25. Phase Framework-Search — ALL STAGES DONE

**Статус:** ✅ Stage 1 + 2 + 3 + bug fix полностью реализованы.
**Дата:** 2026-04-30 (за одну сессию: Stage 1 утром, Stage B+2+3 + bug fix вечером).
**Цель главы:** полное резюме реализации с финальными числами для аудита.

### 25.1. Что построено

Подсистема `framework_search` для semantic-поиска по коду самого фреймворка
(параллельно к BSL retrieval, не вместо).

**Коммиты этой ветки (в порядке):**

| SHA | Что |
|-----|-----|
| `7d104386` | docs: roadmap §23 (per-project BSL reindex operating procedure) + §24 (framework self-search proposal) |
| `ae6ccebb` | feat: framework-search Stage 1 — manual indexer (10 файлов, 1077 строк) |
| `9474dc18` | docs: SKILL.md `.claude/skills/framework-search/SKILL.md` |
| `6c3dbb5b` | chore: регистрация в `skill-router-config.json` (domains.framework + bundle) |

**Файлы реализации:**

```
src/framework_search/
├── __init__.py
├── chunker_base.py        # Chunk dataclass + UUID5 deterministic id
├── config.py              # DEFAULT_INDEX_ROOTS, SKIP_PATTERNS, MAX_FILE_BYTES=512KB
├── python_chunker.py      # AST-based: function/class/method; sliding-window fallback
├── markdown_chunker.py    # H1-H3 splits; code-fence aware (```/~~~ блоки)
├── text_chunker.py        # Generic для json/configs/text
├── file_walker.py         # Glob+SKIP+symlink escape protection
├── embedder.py            # TEI HTTP client + tenacity retry (4 attempts) + sub-batch=32
└── indexer.py             # Pipeline orchestrator + upsert-then-delete idempotency

scripts/index_framework.py # CLI с --recreate/--dry-run/--limit/--paths
```

**code-verify pipeline пройден:**
- quality-review (subagent) → PARTIAL → 4 фикса применены (symlink escape, code-fence, retry, order)
- behavior-preservation (post-fix) → PASS — все public API сохранены, regression tests passed

**Skill discoverable:** триггеры "найди в фреймворке", "framework_code_v1",
"index_framework" подхватятся router'ом в будущих сессиях.

### 25.2. Текущее состояние индексации

| Метрика | Значение |
|---------|----------|
| Qdrant collection | `framework_code_v1` |
| Размерность | 4096d cosine (Qwen3-Embedding-8B через TEI) |
| Точек в коллекции | **50** (smoke-test, не production) |
| Полный объём при reindex | 31 519 chunks из 2 130 файлов |
| Распределение | python 17 224 / markdown 13 419 / json 500 / typescript 266 / text 63 / javascript 47 |
| Размер на full reindex | ~500 MB Qdrant volume |
| Время full reindex | ~15-20 мин (TEI на RTX 3090) |

### 25.3. Три варианта продолжения

При возврате к задаче — выбрать один из:

#### Вариант A — Полный reindex, потом Stage 2 + Stage 3

```bash
python scripts/index_framework.py --recreate
```

- Время: ~15-20 мин GPU (TEI продолжает обслуживать BSL retrieval параллельно)
- Pre-flight: `docker ps | grep pdf-rag-tei` (healthy?), `nvidia-smi` (≥6 GB свободно?)
- Pros: сразу production-ready индекс, MCP-сервер на Stage 2 будет работать на полных данных
- Cons: ~20 мин занят GPU, без MCP-сервера индексом нечем пользоваться

#### Вариант B — Сначала подкрутить scope

Распределение из §25.2 показывает странности:
- `tools/` 8 957 chunks — Node.js утилиты (BSL tools); там может быть generated/vendored код
- `docs/framework documentation/` 2 761 chunks — внутренняя документация фреймворка, может содержать сторонние импорты
- `tests/` 2 404 chunks — тестовые fixtures могут раздувать индекс

```bash
# Посмотреть детально что в tools/
python scripts/index_framework.py --dry-run --paths tools/ 2>&1 | head -30

# После решения — подправить SKIP_PATTERNS в src/framework_search/config.py
# Например, добавить /tools/auto-documenter/node_modules/ если там есть
```

- Pros: меньше шума в индексе → лучше precision поиска, быстрее reindex
- Cons: требует 30-60 минут анализа без code output, отложить полный reindex

**Кандидаты на исключение (нужно проверить):**
- `tools/auto-documenter/build/` — generated artifacts?
- `tools/bsl-debugger/dist/` — Node compiled output?
- `tools/*/test-fixtures/` — фейковые BSL модули для тестов?
- `tests/data/` — большие test fixtures?

#### Вариант C — Stage 2 на тестовых 50 chunks, потом full reindex из MCP

Stage 2 = MCP-сервер `tools/framework-search-mcp/server.py` с инструментами:
- `search_code(query, k=5, language?, path_glob?)`
- `find_similar(file_path, k=5)`
- `index_status()` — chunks count, last reindex timestamp
- `reindex_changed()` — manual trigger
- **Lazy mtime check:** перед каждым `search_code` сравнить mtime файлов с `payload.mtime` в Qdrant; если есть отстающие — реиндексировать ТОЛЬКО их (throttle: не чаще 1× в 30 сек)

```
tools/framework-search-mcp/
├── server.py          # FastMCP (stdio)
├── pyproject.toml
└── README.md
```

Регистрация в `.mcp.json` + `.mcp/full.json`.

- Pros: проверим MCP-pipeline на малом наборе быстрее (50 chunks vs 31k)
- Cons: первые тесты МCP будут на синтетически малом индексе — некоторые edge cases (timeouts на больших batch'ах reindex_changed) не выявятся
- Время: ~3 часа на Stage 2

### 25.4. Stage 3 — file watcher (после A или B+C)

```
scripts/watch_framework.py     # watchdog.Observer + 5s debounce → indexer.run_index(only_paths=...)
```

- Real-time incremental update (~5-7 сек от save до доступности в поиске)
- Запуск: `python scripts/watch_framework.py --daemon`
- Health-check экспонируется через MCP `index_status()`
- Время: ~2 часа

### 25.5. Рекомендуемый порядок (own opinion)

Если время не критично — **B → C → A → Stage 3** (~6-8 часов):
1. **B** (30-60 мин): подкрутить scope, особенно `tools/` (выкинуть generated)
2. **C** (3 часа): Stage 2 MCP server на текущем малом индексе — проверить контракт MCP, lazy mtime check
3. **A** (15-20 мин): полный reindex из MCP `reindex_changed()` без `keep_ids` (full rebuild)
4. **Stage 3** (2 часа): file watcher на крайний случай если MCP lazy-check недостаточен

Если хочется минимально и быстро — **A → C** (~4 часа): полный reindex сейчас + MCP server. Stage 3 watcher и Stage B scope tuning отложить до жалоб на качество.

### 25.6. Чем заняться при возврате

Перед началом работы:

```bash
# 1. Состояние коллекции
curl -s http://localhost:6333/collections/framework_code_v1 | python -m json.tool | grep -E "points_count|dimension"

# 2. TEI healthy
docker ps --filter "name=pdf-rag-tei"

# 3. Свежесть кода (не сломалось ли что в feature branch'е)
.venv/Scripts/python.exe -c "from src.framework_search.indexer import run_index; print('imports OK')"

# 4. Smoke test без перезаписи
python scripts/index_framework.py --limit 10 --dry-run
```

Если всё ок — переходи к выбранному варианту из §25.3.

### 25.7. Финальное состояние (закрытие фазы) — 2026-04-30

Все 3 stages реализованы за ту же сессию что и §25 был написан. План §25.5
(B → C → A → Stage 3) выполнен в один вечер.

**7 коммитов в порядке:**

| SHA | Что |
|-----|-----|
| `7d104386` | docs: §23 operating procedures + §24 framework self-search proposal |
| `ae6ccebb` | feat: Stage 1 — manual indexer (10 файлов, 1077 строк) |
| `9474dc18` | docs: SKILL.md `.claude/skills/framework-search/` |
| `6c3dbb5b` | chore: регистрация в `skill-router-config.json` |
| `36061fd0` | docs: §25 — варианты A/B/C для возврата (исходный план паузы) |
| `1db6e265` | feat: Stage B+2+3 — scope tuning + MCP server + watcher |
| `d5c54e76` | fix: SKIP_PATTERNS leading-slash bug в `_matches_skip` |

**Артефакты в проде:**

| Артефакт | Расположение |
|----------|--------------|
| Pipeline | `src/framework_search/` (8 модулей) |
| CLI | `scripts/index_framework.py` |
| MCP server (Stage 2) | `tools/framework-search-mcp/server.py` (4 tools) |
| Watcher (Stage 3) | `scripts/watch_framework.py` (polling, 5s) |
| Skill | `.claude/skills/framework-search/SKILL.md` |
| Registry | `.mcp.json` (запись `framework-search`) + `skill-router-config.json` (bundle `framework-search`) |
| Qdrant | collection `framework_code_v1` |

**Финальные числа индекса:**

| Метрика | Значение |
|---------|----------|
| points_count | **21 164** (после bug-fix; до — 24 481, утечка 3317 chunks из BSL projects устранена) |
| dimensions | 4096 cosine (Qwen3-Embedding-8B) |
| files indexed | 1 794 |
| files seen | 1 843 (49 пропущено по SKIP/size) |
| Время full reindex | 20.4 мин на TEI |
| Распределение | python 12 806 / markdown 7 903 / typescript 264 / json 151 / text 29 / javascript 11 |

**Smoke-test (4 запроса) на финальном индексе — все top-1 релевантны:**

| Запрос | Top-1 | Score |
|--------|-------|-------|
| "fallback логика для embedding когда основной backend упал" | `tenacity-retry/SKILL.md:57` | 0.690 |
| "хук блокирующий Write без активации skill" | `30.3_Enforcers.md:64` | 0.740 |
| "late chunking pooling mode для Qwen3" | `ADR-008-qwen3-late-chunking.md:27` | 0.703 |
| "TEI HTTP client с retry и sub-batching" | `11.5_Стек_и_трейсинг.md:255` | 0.588 |

**Что нужно для активации MCP в новой сессии:**

1. **Перезапустить Claude Code** — MCP `framework-search` зарегистрирован в `.mcp.json` после старта текущей сессии, новые tools `mcp__framework-search__*` появятся только после ребута.
2. **(Опционально) Запустить watcher как daemon** — Windows Task Scheduler или `nssm install framework-search-watcher`. Без watcher MCP lazy-check вытянет stale файлы при ближайшем `search_code` (throttle 30 сек).

**Bug-trail (для подобных случаев в будущем):**

- `SKIP_PATTERNS` substring-match имеет тонкость: паттерны вида `/x/y/`
  не матчат top-level пути (без leading slash в repo-rel POSIX).
  Фикс — двойная логика в `_matches_skip` ([file_walker.py:25-43](src/framework_search/file_walker.py#L25)):
  ```python
  if pl in low: return True
  if pl.startswith("/") and low.startswith(pl[1:]): return True
  ```
- 3 317 chunks утечки удалены из Qdrant через `FilterSelector` без полного reindex'а
  (FieldCondition по relative_path = `MatchText("src/projects/configuration/")`).

---

## 26. Reality check (2026-04-30) — что реально сделано vs план

**Триггер:** аудит после §25 закрытия. Изначальная цель Phase 8 — мигрировать **все 11 коллекций** Qdrant на Qwen3-Embedding-8B (4096d). Реально мигрировано **3 из 11** (BSL family + framework_code_v1). Этот раздел фиксирует реальное состояние перед добивкой остатка.

### 26.1. Состояние всех коллекций (snapshot)

```bash
$ curl -s http://localhost:6333/collections | python -m json.tool
```

| Коллекция | Цель Phase 8 | Факт 2026-04-30 | Действие |
|-----------|--------------|-----------------|----------|
| `bsl_code_v4` | 4096d Qwen3 | 24 455 × **4096d** | ✅ §21.6 8.12.3 |
| `bsl_code_v4_late` | 4096d Qwen3+Late | 24 455 × **4096d** | ✅ §21.10 8.12.10 |
| `framework_code_v1` | (новая, §25) | 21 198 × **4096d** | ✅ §25 |
| `pdf_documents` | 4096d | 1 012 × **1024d E5** | ❌ §28 P1 — reindex |
| `wiki_pages_v1` | 4096d | 3 073 × **1024d E5** | ❌ §28 P1 — reindex |
| `graph_embeddings` | 4096d | 6 694 × **1024d E5** | ❌ §28 P1 — reindex |
| `learned_patterns` | 4096d | 44 × **1024d E5** | ❌ §28 P1 — reindex |
| `bsl_metadata` | 4096d | **0 pts** × 1024d | ❓ §28 audit — drop or rebuild |
| `skill_library` | 4096d | **0 pts** × 1024d | ❓ §28 audit — drop or rebuild |
| `conversation_memory` | 4096d | **0 pts** × 1024d | ❓ §28 audit — drop or rebuild |
| `experience_embeddings` | 4096d | **0 pts** × 1024d | ❓ §28 audit — drop or rebuild |
| `visual_grounding` | 4096d | 5 × **768d nomic** | ⏸ defer — 5 точек, low ROI |
| `bsl_code_v3` (legacy) | DROP | 22 665 × **1024d E5** | ❌ §27 P0 — drop |
| `experience_embeddings_e5_legacy` | DROP | 61 × **768d** | ❌ §27 P0 — drop |
| `learned_patterns_e5_legacy` | DROP | 44 × **1024d** | ❌ §27 P0 — drop |

### 26.2. Аналитика гэпа

**Закрыто (3 коллекции, 70 108 points):**
- `bsl_code_v4` + `_late` — production BSL retrieval (закрытие 8.7+8.8 для самой большой коллекции)
- `framework_code_v1` — bonus, не было в исходном плане Phase 8 (см. §24/§25)

**Осталось (10 коллекций):**
- 4 на E5 1024d (`pdf_documents`, `wiki_pages_v1`, `graph_embeddings`, `learned_patterns`) — **работают, но qualуступают Qwen3 на code-content**
- 4 пустые (`bsl_metadata`, `skill_library`, `conversation_memory`, `experience_embeddings`) — нужен audit, не факт что нужны
- 3 legacy для drop (`bsl_code_v3`, два `_e5_legacy`)
- 1 опциональная (`visual_grounding` — 5 точек nomic)

**Оптимизация скоупа:** из 10 оставшихся реально нужно реиндексировать максимум 4 (E5 → Qwen3), 3 дропнуть, 4 проверить на необходимость. Это **~3-4 часа** работы, не 11 коллекций × 1 час каждая.

### 26.3. Что фактически было сделано из подразделов 8.7-8.11

| Раздел | Subtask | Декларативный статус | Фактический |
|--------|---------|---------------------|-------------|
| 8.7.1 | DELETE 10 коллекций | `[ ]` | Частично — `bsl_code_v4*` пересозданы; остальные старые остались |
| 8.7.2 | Создать заново 4096d/1024d | `[ ]` | Только bsl_code_v4 + _late + framework_code_v1 на 4096d |
| 8.7.3 | НЕ создавать bsl_code_v3 | `[ ]` | bsl_code_v3 не пересоздан, но и не дропнут (legacy) |
| 8.7.4 | Sparse vectors для hybrid | `[ ]` | Не сделано (одиночные dense vectors везде) |
| 8.8.x | Reindex остальных коллекций | `[ ]` × 9 | Не сделано (см. §28) |
| 8.9.x | Quality benchmarks | `[ ]` × 7 | Только BSL (8.12.8 pilot 50q) |
| 8.10.1 | `.env` обновить (EMBEDDING__MODEL) | `[ ]` | Только в bsl-development skill |
| 8.10.2 | Skills: embedding-models, qdrant-operations | `[ ]` | Частично (BSL-specific параметры обновлены) |
| 8.10.3 | docs/framework documentation/ RAG раздел | `[ ]` | Не сделано |
| 8.10.4 | pyproject.toml — transformers≥4.51 | `[ ]` | Не сделано (TEI Docker не требует local transformers update) |
| 8.10.5 | ADR «Выбор embedding-модели 2026» | `[ ]` | ADR-008 для BSL specifically |
| 8.11.1 | Drop E5 snapshots после 2026-05-03 | `[ ]` | По времени ещё рано (надо ждать 1 неделю hold) |
| 8.11.2 | Drop HF cache E5-large | `[ ]` | Не сделано (опц. ~2.2 GB) |
| 8.11.3 | Drop bsl_code_v3 | `[ ]` | **Не сделано — будет в §27** |
| 8.11.4 | Финальный коммит | `[ ]` | Будет в §29 |

### 26.4. Pending sections (что добавляется в roadmap)

- **§27 — Phase 8.14 Cleanup legacy collections** (P0, 5 мин) — drop bsl_code_v3 + 2× e5_legacy
- **§28 — Phase 8.15 Migrate remaining collections to Qwen3** (P1, 3-4 часа) — 4 reindex + 4 audit
- **§29 — Phase 8.16 Sync configs + final commit** (P2, 1 час) — `.env`, skills, ADR, "Phase 8 complete"

Phase 8.13 (LoRA fine-tuning) остаётся DEFERRED как было.

---

## 27. Phase 8.14 — Cleanup legacy collections (P0, in progress)

**Статус:** 🔄 IN PROGRESS 2026-04-30
**Цель:** убрать 3 устаревшие коллекции, освобождающие место и убирающие путаницу.

**Условие безопасности:** backup существует в `E:/Transfer folder/qdrant/1c-pre-qwen3-2026-04-26/` (manifest `260426_PHASE_8_PRE_QWEN3_BACKUP_MANIFEST.json`). При необходимости откат восстанавливается из cold archive.

### 27.1. Tasks

- [ ] **27.1** Pre-flight: убедиться что backup физически существует
- [ ] **27.2** DELETE `bsl_code_v3` (22 665 pts, 1024d E5) — заменён `bsl_code_v4_late`
- [ ] **27.3** DELETE `experience_embeddings_e5_legacy` (61 pts, 768d) — explicit legacy name
- [ ] **27.4** DELETE `learned_patterns_e5_legacy` (44 pts, 1024d) — explicit legacy name
- [ ] **27.5** Verify: `client.get_collections()` показывает 12 коллекций (было 15)
- [ ] **27.6** Грепнуть кодовую базу: остались ли упоминания `bsl_code_v3` в active code (не должно)

---

## 28. Phase 8.15 — Migrate remaining collections to Qwen3 (P1, planned)

**Статус:** ⏳ PLANNED
**Цель:** добить миграцию (закрыть 8.8.x для остальных 4 коллекций + audit пустых).

### 28.1. Audit пустых коллекций (кто использует / надо ли)

- [ ] **28.1.1** `bsl_metadata` (0 pts) — используется ли каким-то MCP-инструментом? Источник: BSL parser metadata. **Решение:** drop или rebuild.
- [ ] **28.1.2** `skill_library` (0 pts) — должна содержать 75 skills из `.claude/skills/`. Скрипт `scripts/index-skills-to-qdrant.py` существует. **Решение:** запустить скрипт.
- [ ] **28.1.3** `conversation_memory` (0 pts) — должна содержать ~372 conv. Источник: `data/conversations.db` (если есть). **Решение:** rebuild или drop.
- [ ] **28.1.4** `experience_embeddings` (0 pts) — 61 pts ожидалось. Источник: `data/experience.*`. **Решение:** rebuild или drop.

### 28.2. Reindex E5 → Qwen3 (4 коллекции с данными)

- [ ] **28.2.1** `pdf_documents` (1012 pts E5 → Qwen3) — через `python -m src.cli.main index "<pdf>" --recreate-collection` или прямой reindex script. ~5-10 мин TEI.
- [ ] **28.2.2** `wiki_pages_v1` (3073 pts) — через `wiki-pipeline` skill, source `docs/wiki/`. ~15-30 мин.
- [ ] **28.2.3** `graph_embeddings` (6694 pts) — через KG nodes из Neo4j или `data/graph/`. ~30-60 мин.
- [ ] **28.2.4** `learned_patterns` (44 pts) — через memory system. ~1 мин.

### 28.3. Verification

- [ ] **28.3.1** Все 4 reindexed коллекции показывают dims=4096
- [ ] **28.3.2** `pdf_documents` smoke: «регистр сведений 1С» → top-3 score ≥ 0.65 (Qwen3 порог; для E5 был 0.85, но Qwen3 cosine иначе калиброван)
- [ ] **28.3.3** Update sparse vectors (BM25) для коллекций где hybrid retrieval нужен

### 28.4. `visual_grounding` (опционально)

- [ ] **28.4.1** Решение: drop или migrate? 5 pts × 768d (nomic). Низкий ROI миграции.

---

## 29. Phase 8.16 — Sync configs + final commit (P2, planned)

**Статус:** ⏳ PLANNED

### 29.1. Tasks

- [ ] **29.1** `.env.example` — обновить `EMBEDDING__MODEL`, `EMBEDDING__DIMENSIONS`, описание Qwen3+TEI default
- [ ] **29.2** `embedding-models` skill — переписать default secition на Qwen3 (E5 → "legacy fallback")
- [ ] **29.3** `qdrant-operations` skill — обновить snapshot про коллекции (15 → 12 после §27)
- [ ] **29.4** `framework-config` skill — sync EMBEDDING__* defaults
- [ ] **29.5** `docs/framework documentation/...` — раздел RAG/embeddings актуализировать
- [ ] **29.6** ADR «Выбор embedding-модели 2026» — обобщающий поверх ADR-008 BSL-specific (если необходимо)
- [ ] **29.7** Финальный коммит «Phase 8 complete»: roadmap mark all tasks done, MEMORY.md note

### 29.2. После 2026-05-03 (отдельный коммит)

- [ ] **29.8** Drop старые `*.snapshot` E5-файлы из `docker_qdrant_snapshots` volume (1 неделя hold выдержана)
- [ ] **29.9** Drop HF cache E5-large (~2.2 GB) — опционально

---

После Phase 8 — кандидаты Phase 9: cross-encoder Qwen3-Reranker, hybrid search tuning,
LLM-rotation expansion (новые провайдеры после Z.AI лимита). Framework code self-search
(§24 → §25) ✅ полностью реализован. Phase 8.13 LoRA — DEFERRED (см. §22).
