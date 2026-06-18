# 02 — Дизайн: veto НЕ-1С тех-контекста

## `_NON_1C_CONTEXT` (denylist, калиброван)
Высокоточные маркеры НЕ-1С разработки (re.I). Категории:
- **Python/web:** fastapi, apirouter, uvicorn, pytest, conftest, asyncio, httpx, pydantic, django, flask, numpy, pandas, typescript, javascript, react, jest, node, golang, rust.
- **RAG/ML:** эмбеддинг/embedding, qdrant, chromadb, faiss, langchain, langgraph, rerank/reranker, ragas, bm25, tei, sparse vector, vector store, векторн, трансформер, attention, llm.
- **Infra/devops:** docker, kubernetes/k8s, redis, postgres, mysql, mongo, nginx, s3 bucket, grafana, prometheus, webhook, oauth, dns, github actions, ci/cd, ci, pipeline, grpc, graphql, reverse proxy, alembic, loguru, requirements.
- **Repo/прочее:** duckdb, hook-invocations, tech-research, skill-router, memory-first, .env, .py, regex, микросервис, пагинац, бэкенд, фронтенд, стектрейс, readme, search pipeline.

**Исключено намеренно** (неоднозначно / реальный 1С): `rmq/rabbitmq/kafka` (1С-обмен через очередь),
`mcp` (1c-mcp), голый `api`, `база данных`.

## `_has_non_1c_context(prompt) -> bool`
`bool(_NON_1C_CONTEXT.search(prompt or ""))`. best-effort, не кидает.

## Veto в `route_1c_task`
```
confident = cl.confidence >= 0.7
... семантика только если не confident ...
is_1c = cl.is_1c or semantic_hit
non_1c_ctx = (not confident) and is_1c and _has_non_1c_context(prompt)   # veto-флаг
if non_1c_ctx:
    is_1c = False        # слабый 1С-сигнал перевешен явным НЕ-1С тех-контекстом
if not is_1c:
    return {... flow:"none", reason: (non_1c_ctx ? "НЕ-1С тех-контекст перевесил слабый 1С-сигнал"
                                                  : "не 1С-задача"), non_1c_context: non_1c_ctx}
... остальные ветки: добавить ключ non_1c_context (False) ...
```
Ключ `non_1c_context` — во ВСЕХ возвратах (наблюдаемость + тесты).

## Почему veto, а не downgrade до ask
Denylist высокоточен (FastAPI/Qdrant/pytest 1С-задача не содержит) — это **улика против**, а не
«сомнение». Сомнение → ask; улика-против → none. Confident-исключение гарантирует: настоящая 1С-задача,
случайно упомянувшая тех-слово, имеет JIRA/код/гкс_/CamelCase → не ветируется. Калибровка подтвердила
0 потерь recall.

## Риски и откат
- Риск: 1С-задача со слабым сигналом + случайным denylist-словом → none. Митигировано исключением
  неоднозначных слов + confident-override; замерено 0 на GT и holdout. Остаточно: «настроить обмен
  через kafka в 1С» без JIRA → kafka исключён → НЕ ветируется (ask_1c). ОК.
- Откат: удалить `_NON_1C_CONTEXT` + 3 строки veto в route. Аддитивно, 1 файл кода.
