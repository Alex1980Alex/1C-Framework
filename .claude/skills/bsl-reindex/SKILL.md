---
name: bsl-reindex
description: "Реиндекс BSL/кода в Qdrant (НЕ PDF). ИСПОЛЬЗУЙ при реиндексе 1С-конфигурации/эталонов (bsl_code_*) или фреймворк-кода (framework_code_v1): выбор backend, устойчивый прогон, типичные ошибки. Триггеры: 'реиндекс bsl', 'проиндексировать конфигурацию', 'переиндексировать конфигурацию', 'supervised reindex', 'reindex_bsl_qwen3', 'reindex_supervised', 'bsl_code_erp_ref', 'reference_1c_code', 'index_framework', 'CUDA wedge при индексации'. Делегирует гл.31 + ADR-038, методику не дублирует. НЕ для PDF (→ indexing-pipeline)."
version: 1.0.0
updated: 2026-06-24
---

# bsl-reindex — реиндекс BSL/кода (оркестратор)

> **Паттерн (как `fix-sonar-task`):** это **указатель-оркестратор**. Полная методика — в
> [гл. 31.3 Pipeline индексации](../../../docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.3_Pipeline_индексации.md),
> [гл. 31.6 Варианты и ошибки](../../../docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md),
> [ADR-038](architecture-research/adr/038-resilient-erp-reindex-batch1-supervisor.md). Здесь — решение
> «что запустить» + хард-правила; детали не дублируются.

## Когда использовать
- Реиндекс 1С-конфигурации / эталонов ERP/UT (`bsl_code_*`, `bsl_code_erp_ref`, `reference_1c_code`).
- Реиндекс фреймворк-кода (`framework_code_v1`).
- «Завис реиндекс / CUDA-wedge / OOM при индексации», выбор backend/флагов, устойчивый прогон.
- **НЕ** для PDF-документов → `indexing-pipeline`. Анализ ПОСЛЕ прогона → `post-indexing-analysis`.

## Карта коллекций (что куда)
| Коллекция | Источник | Индексатор |
|---|---|---|
| `bsl_code_v4_late` (alias→`_v3`, hybrid dense+bm25) | 1С-конфиги (`ИБ…/Конфигурация` и др.) | `reindex_bsl_qwen3.py` |
| `bsl_code_erp_ref` | `external/1c-reference-src/erp` (BSL) | `reindex_bsl_qwen3.py` / `reindex_supervised.py` |
| `reference_1c_code` | `external/1c-reference-src/trade` (BSL) | `reindex_bsl_qwen3.py` |
| `framework_code_v1` (alias→`_mrl_1024`) | src/docs/.claude/tools/tests/scripts (**external/ исключён**) | `scripts/index_framework.py` |

## Решение: какой backend
- **Full reindex** (`--project <root>`) → **`qwen3-st`** (Late Chunking) + **обязательно `--no-region-aware`** (region-aware = −25pp recall@10). **STOP TEI перед запуском** (`docker stop pdf-rag-tei`; один GPU = OOM с двумя Qwen3-8B), вернуть после.
- **Incremental** (`--paths …`/git post-commit) → **`qwen3-tei`** (TEI остаётся up; std-pool, mixed-quality acceptable).
- Дефолт query mode коллекций — **hybrid DBSF** (см. гл. 31.7), к индексации флагом не относится.

## Устойчивый full reindex (ADR-038) — РЕКОМЕНДУЕМЫЙ способ для больших/ERP
Тихий **CUDA-wedge** Qwen3-8B на тяжёлых модулях (монстры >2MB и крупные <2MB) лечится тремя частями.
Запускать **под супервизором**:
```bash
docker stop pdf-rag-tei
python scripts/reindex_supervised.py \
    --project "<ABS-path>" --collection bsl_code_erp_ref \
    --max-file-bytes 2097152 --long-batch1-tokens 1024
docker start pdf-rag-tei
```
- **Part A** `--long-batch1-tokens 1024` — batch=1 для длинных чанков (профилактика wedge).
- **Part B** супервизор — **stall-watchdog по росту points** (НЕ idle!) + лестница batch 32→8→1 + resume.
- **Part C** `--max-file-bytes` → монстры в `data/reports/reindex_deferred.txt`; доиндексация:
  `python scripts/reindex_bsl_qwen3.py --paths-file data/reports/reindex_deferred.txt --batch-size 1 --embedder qwen3-st --collection <c> --enable-sparse`.

## Хард-правила (типичные ошибки — детали гл. 31.6 §6)
- **НЕ** ставить `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` — на Windows WDDM reserved растёт → BSOD + перебивает тюнинг скрипта → зависание. Скрипт сам ставит `garbage_collection_threshold:0.6,max_split_size_mb:512`.
- Full reindex `qwen3-st` **всегда** с `--no-region-aware`.
- `qwen3-st` только после `docker stop pdf-rag-tei` (проверить `nvidia-smi` <2GB).
- `--recreate` дропает ВСЮ коллекцию — только при breaking-changes payload/модели; для добавления проекта НЕ нужен (доupsert).
- BSL = MRL **REJECT** (хранить 4096d); SQ int8 — можно.
- Liveness прогона = **рост points** (`/points/count`), а НЕ heartbeat-`idle` в логе (idle сломан, всегда растёт).
- `build_call_graph.py` ДО reindex (иначе `calls`/`caller_count` пустые).

## Связанное
- Доки: гл. 31.3 / 31.6 / 31.7; скрипты [`reindex_bsl_qwen3.py`](../../../scripts/reindex_bsl_qwen3.py), [`reindex_supervised.py`](../../../scripts/reindex_supervised.py), [`index_framework.py`](../../../scripts/index_framework.py).
- Решение: [ADR-038](architecture-research/adr/038-resilient-erp-reindex-batch1-supervisor.md).
- Память: `feedback_qwen3_embedding_wedge_heavy_modules`, `feedback_bsl_indexer_backend_choice`, `feedback_mrl_content_matters`.
- Скиллы: `post-indexing-analysis` (отчёт после), `embedding-models`/`qdrant-operations` (модели/коллекции), `indexing-pipeline` (PDF — другое).
