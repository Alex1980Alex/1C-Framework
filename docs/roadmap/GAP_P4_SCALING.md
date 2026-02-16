# P4 — Масштабирование

**Effort:** 5-8 дней | **Impact:** MEDIUM-LOW | **Phases:** 59-61
**Зависимости:** P2 (Docker, Neo4j) для S1, S3.

---

## S1 — Async Processing Queue (Phase 59)

**Текущее:** Indexing — синхронный (одна PDF за раз, concurrency guard). Stream endpoint (`/index-stream`) отправляет NDJSON events. Background tasks через `asyncio.create_task()`.
**Gap:** Нет persistent queue. При crash — потеря progress. Нет priority scheduling. Нет retry с backoff.

### S1.1 Task queue setup

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S1.1.1 | Добавить `arq` в dependencies (Redis-based, async) | `pyproject.toml` | +1 | `pip install .[queue]` |
| S1.1.2 | Создать `WorkerSettings` config | `src/pdf_framework/config/infrastructure.py` | +8 | Config loads |
| S1.1.3 | Конфиг: `QUEUE__REDIS_URL`, `QUEUE__MAX_JOBS`, `QUEUE__TIMEOUT` | Тот же файл | +4 | Defaults set |
| S1.1.4 | Создать worker entry point | `src/pdf_framework/workers/worker.py` | ~40 | Worker starts |

---

### S1.2 Task definitions

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S1.2.1 | Task: `index_document(file_path, options)` | `src/pdf_framework/workers/tasks/indexing.py` | ~60 | Task completes |
| S1.2.2 | Task: `rebuild_bm25(document_id)` | `src/pdf_framework/workers/tasks/indexing.py` | ~20 | BM25 rebuilt |
| S1.2.3 | Task: `rebuild_graph(document_id)` | `src/pdf_framework/workers/tasks/graph.py` | ~30 | Graph rebuilt |
| S1.2.4 | Task: `rebuild_embeddings(document_id)` | `src/pdf_framework/workers/tasks/indexing.py` | ~30 | Embeddings rebuilt |
| S1.2.5 | Task: `run_evaluation(dataset_path)` | `src/pdf_framework/workers/tasks/evaluation.py` | ~30 | Evaluation runs |
| S1.2.6 | Progress callback: update job status (0-100%) | `src/pdf_framework/workers/progress.py` | ~30 | Progress tracked |
| S1.2.7 | Retry logic: 3 attempts, exponential backoff | Config в WorkerSettings | ~5 | Retry works |

---

### S1.3 API integration

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S1.3.1 | POST `/documents/index-async` → enqueue job | `src/api/routes/documents.py` | +20 | Job ID returned |
| S1.3.2 | GET `/jobs/{job_id}` → job status + progress | `src/api/routes/jobs.py` | ~40 | Status returned |
| S1.3.3 | GET `/jobs` → list active/recent jobs | `src/api/routes/jobs.py` | ~20 | List works |
| S1.3.4 | DELETE `/jobs/{job_id}` → cancel job | `src/api/routes/jobs.py` | ~15 | Job cancelled |
| S1.3.5 | Регистрация router в app.py | `src/api/app.py` | +2 | Route active |
| S1.3.6 | SSE endpoint: `/jobs/{job_id}/stream` → progress events | `src/api/routes/jobs.py` | +30 | Events stream |

---

### S1.4 Docker integration

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S1.4.1 | Worker service в docker-compose | `docker/docker-compose.yml` | +15 | Worker starts |
| S1.4.2 | Shared volume для data/ (api + worker) | `docker/docker-compose.yml` | +3 | Data shared |
| S1.4.3 | Health check для worker | `docker/docker-compose.yml` | +5 | Worker healthy |
| S1.4.4 | Unit test: task enqueue + execute | `tests/unit/workers/test_tasks.py` | ~50 | — |
| S1.4.5 | Integration test: async indexing via API | `tests/integration/test_async_indexing.py` | ~60 | — |

**Acceptance:** `POST /documents/index-async` → job ID. `GET /jobs/{id}` → progress. Worker processes jobs from Redis queue.

---

## S2 — Multi-tenant Isolation (Phase 60)

**Текущее:** JWT с tenant_id. RBAC (3 роли). Qdrant collection per-KB (Phase 32). Нет data isolation per tenant.
**Gap:** Все tenants в одной Qdrant collection `pdf_chunks`. Нет isolation. Нет per-tenant quotas.

### S2.1 Tenant-scoped storage

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S2.1.1 | Qdrant: добавить `tenant_id` в payload всех chunks | `src/pdf_framework/vector_store/providers/qdrant.py` | +10 | Payload includes tenant |
| S2.1.2 | Search: автоматический filter по tenant_id | `src/pdf_framework/vector_store/providers/qdrant.py` | +15 | Isolation enforced |
| S2.1.3 | BM25 FTS5: добавить tenant_id column | `src/pdf_framework/search/bm25_store.py` | +10 | FTS5 schema updated |
| S2.1.4 | BM25 search: WHERE tenant_id = ? | `src/pdf_framework/search/bm25_store.py` | +5 | Filter works |
| S2.1.5 | Graph: tenant_id на entities/relations | `src/pdf_framework/graph_store/base.py` | +5 | Schema updated |
| S2.1.6 | Graph: filter по tenant_id | `src/pdf_framework/graph_store/providers/networkx_store.py` | +10 | Isolation |

---

### S2.2 Tenant management API

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S2.2.1 | POST `/tenants` → create tenant | `src/api/routes/tenants.py` | ~20 | Tenant created |
| S2.2.2 | GET `/tenants` → list tenants (admin only) | Тот же файл | ~15 | List works |
| S2.2.3 | GET `/tenants/{id}/stats` → documents, chunks, storage | Тот же файл | ~25 | Stats returned |
| S2.2.4 | DELETE `/tenants/{id}` → delete all data (admin only) | Тот же файл | ~20 | Cleanup complete |
| S2.2.5 | Регистрация router | `src/api/app.py` | +2 | Route active |

---

### S2.3 Quotas

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S2.3.1 | Создать `TenantQuota` model | `src/pdf_framework/schemas/tenant.py` | ~20 | Schema |
| S2.3.2 | Limits: max_documents, max_chunks, max_queries_per_day | Тот же файл | ~10 | Fields |
| S2.3.3 | Enforcement: check quota before indexing | `src/pdf_framework/indexing/indexer.py` | +10 | Quota blocked |
| S2.3.4 | Enforcement: check quota before search | `src/pdf_framework/search/manager.py` | +10 | Quota blocked |
| S2.3.5 | Конфиг: default quotas | `src/pdf_framework/config/infrastructure.py` | +5 | Defaults set |
| S2.3.6 | Unit test: quota enforcement | `tests/unit/test_tenant_quotas.py` | ~40 | — |
| S2.3.7 | Integration test: tenant isolation | `tests/integration/test_multi_tenant.py` | ~60 | — |

**Acceptance:** Tenant A не видит данные Tenant B. Quotas enforcement. Admin API.

---

## S3 — Incremental Graph Update (Phase 61)

**Текущее:** `IncrementalGraphUpdater` в `graph_store/incremental.py` — merge entities, detect affected communities, re-summarize. Работает, но только для NetworkX.
**Gap:** Нет incremental update для entity embeddings (LightRAG). Нет partial re-extraction. Нет change detection.
**Зависимость:** P1 (Neo4j) — incremental updates должны работать и с Neo4j.

### S3.1 Change detection

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S3.1.1 | Создать `GraphChangeDetector` class | `src/pdf_framework/graph_store/change_detector.py` | ~60 | Unit test |
| S3.1.2 | Detect: new chunks (not in graph) | Тот же файл | ~15 | New chunks found |
| S3.1.3 | Detect: modified chunks (content hash changed) | Тот же файл | ~20 | Modified detected |
| S3.1.4 | Detect: deleted chunks (in graph, not in store) | Тот же файл | ~15 | Deleted detected |
| S3.1.5 | Output: `ChangeSet(added, modified, deleted)` | Тот же файл | ~10 | Changeset correct |

---

### S3.2 Partial re-extraction

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S3.2.1 | Extract entities only from changed chunks | `src/pdf_framework/graph_store/incremental.py` | +15 | Partial extraction |
| S3.2.2 | Remove entities from deleted chunks | Тот же файл | +20 | Entities removed |
| S3.2.3 | Re-merge entities from modified chunks | Тот же файл | +15 | Entities updated |
| S3.2.4 | Re-detect communities only for affected subgraph | Тот же файл | +10 | Targeted re-detect |

---

### S3.3 Entity embeddings update

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S3.3.1 | Delete embeddings for removed entities | `src/pdf_framework/graph_store/entity_embeddings.py` | +15 | Points deleted |
| S3.3.2 | Add embeddings for new entities | Тот же файл | +10 | Points added |
| S3.3.3 | Update embeddings for modified entities | Тот же файл | +15 | Points updated |
| S3.3.4 | Batch update: process all changes in one pass | Тот же файл | +10 | Efficient update |

---

### S3.4 API & scheduling

| # | Подзадача | Файл | Строк | Тест |
|---|-----------|------|-------|------|
| S3.4.1 | API: `POST /graph/incremental-update` | `src/api/routes/graph.py` | +20 | API works |
| S3.4.2 | Auto-trigger: after document re-index | `src/pdf_framework/indexing/indexer.py` | +5 | Auto-update |
| S3.4.3 | Конфиг: `GRAPHRAG__AUTO_UPDATE=true/false` | `src/pdf_framework/config/graphrag.py` | +2 | Config |
| S3.4.4 | Unit test: change detection | `tests/unit/graph_store/test_change_detector.py` | ~50 | — |
| S3.4.5 | Unit test: partial re-extraction | `tests/unit/graph_store/test_incremental.py` | ~50 | — |
| S3.4.6 | Integration test: full incremental cycle | `tests/integration/test_graph_incremental.py` | ~60 | — |

**Acceptance:** Re-index документа обновляет только изменённые entities. Entity embeddings синхронизируются. Нет full rebuild.

---

## Чеклист завершения P4

- [ ] ARQ worker processes jobs from Redis
- [ ] API: async indexing, job status, cancel
- [ ] Tenant isolation: Qdrant + BM25 + Graph
- [ ] Tenant API: create, list, stats, delete
- [ ] Quotas: per-tenant limits enforced
- [ ] Graph change detection: added/modified/deleted
- [ ] Partial entity re-extraction (only changed chunks)
- [ ] Entity embeddings incremental update
- [ ] All new code covered by tests
