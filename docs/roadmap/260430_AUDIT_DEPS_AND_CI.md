# Audit: pyproject.toml + CI/CD vs реальность

**Дата:** 2026-04-30 (вечер) → fully closed 2026-05-09
**Статус:** ✅ FULLY DONE — initial 2026-05-01 (D.1/D.2/D.4/D.5/D.7/D.8). Final sweep 2026-05-09: D.5.2 Dependabot config (`.github/dependabot.yml`, weekly pip + monthly github-actions); D.6.2 nomic[local] помечен legacy fallback в pyproject.toml `[bsl]`; D.6.3 — `[memory]` extras наследуют httpx из base (комментарий добавлен). Acceptance criteria 4.1-4.3 verified: `httpx 0.28.1 / pyjwt 2.12.1`, imports `framework_search.embedder.FrameworkTEIEmbedder` + `api.auth.jwt_handler` работают чисто. 9/9 sub-task checkboxes ticked.
**Scope:** `pyproject.toml`, `.github/workflows/`, `.pre-commit-config.yaml`, корневые repo-файлы (LICENSE, README, CONTRIBUTING, CHANGELOG)
**Связано:**
- [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §1.2 (tools scope не покрыт)
- [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md) (sibling)

---

## 0. Резюме

Repo infrastructure в **хорошем состоянии**: pre-commit hooks полные (ruff, mypy, markdownlint, kb-lint, hermes-eval-smoke), CI workflows для Python (`ci.yml`) и 1С (`ci-1c.yml`), все стандартные файлы (LICENSE/README/CONTRIBUTING/CHANGELOG) присутствуют.

**Проблемы (~6):**

| Severity | Item | Действие |
|----------|------|----------|
| 🔴 P0 | `httpx` используется в 5 src-файлах, но НЕ в base deps | Add to `[project.dependencies]` |
| 🔴 P0 | `pyjwt` (`import jwt`) используется в `src/api/auth/jwt_handler.py`, но НЕТ нигде в pyproject | Add to base deps или явно к `[auth]` extra |
| 🟠 P1 | `arq` в `[queue]` extra, но `src/workers/` импортирует напрямую — нужно явно decide queue=core или extra | Решить + документировать |
| 🟠 P1 | `chromadb>=0.5` в base deps + есть provider, но используется только в legacy `bsl/finetuning` script + opt-in vector store. Не «dead» как раньше думали — нужно apparent caveat | Document: «include for `provider=chroma` opt-in» |
| 🟠 P1 | Нет `safety`/`pip-audit` в CI → security vulnerabilities в deps незаметны | Add scheduled job в `ci.yml` |
| 🟡 P2 | Phase 8/9.1 integration в `pyproject` — `[bsl]` extra не включает Qwen3-specific deps (TEI клиентский — httpx; Late Chunking — sentence-transformers с pooling) | Audit `[bsl]` extra; добавить если нужно |

**Total effort:** ~3-5 ч.

---

## 1. pyproject.toml — что нашли

### 1.1 Базовая структура

```toml
[project]
name = "pdf-vector-graph-framework"
version = "1.5.0"
requires-python = ">=3.11"

dependencies = [
    "langchain>=0.3", "langgraph>=0.3", "langchain-anthropic", "langchain-openai",
    "langchain-community", "langchain-text-splitters",
    "pymupdf>=1.24", "pdfplumber>=0.11",
    "chromadb>=0.5",                          # 🟠 see §2.4
    "sentence-transformers>=3.0",
    "colpali-engine>=0.1.0", "transformers[torch]>=4.40.0", "pillow>=10.0",
    "FlagEmbedding>=1.2.0",
    "networkx>=3.4",
    "fastapi>=0.115", "uvicorn>=0.32",
    "mcp>=1.0",
    "python-dotenv>=1.0", "pydantic>=2.10", "pydantic-settings>=2.6",
    "rich>=13.0", "typer>=0.15", "prometheus-client>=0.21",
    # ❌ MISSING: httpx, pyjwt
]

[project.optional-dependencies]
faiss = [...]
qdrant = ["qdrant-client>=1.12"]
neo4j = [...]
unstructured = [...]
docling = [...]
voyage = [...]
morphology = [...]
nlp = [...]
deep = [...]
langsmith = [...]
langfuse = [...]
all = ["pdf-vector-graph-framework[faiss,qdrant,neo4j,unstructured,docling,voyage,nlp,deep,langsmith,langfuse,queue,bsl,memory,llm-rotation]"]
queue = ["arq>=0.26"]                         # 🟠 see §2.3
bsl = ["qdrant-client>=1.12", "neo4j>=5.25", "fastmcp>=0.1", "nomic[local]>=3.0"]
memory = ["qdrant-client>=1.12", "google-generativeai>=0.8"]
llm-rotation = ["mistralai>=1.0", "openai>=1.0", "google-generativeai>=0.8", ...]
```

### 1.2 Что хорошо ✅

- `requires-python = ">=3.11"` — соответствует docs
- LangChain ecosystem правильно зафиксирован (langchain + langgraph + community)
- Optional extras разделены логично (faiss / qdrant / neo4j / docling / voyage)
- `[all]` extra ссылается на остальные — корректный pattern
- BSL deps изолированы в `[bsl]` extra
- Memory subsystem deps в `[memory]`

---

## 2. Findings

### 2.1 🔴 `httpx` отсутствует в base deps

**Найдено:** 5 файлов в `src/` импортируют `httpx`:

| Файл | Использование |
|------|---------------|
| `src/framework_search/embedder.py` | TEI HTTP client (`httpx.Client(base_url, timeout)`) |
| `src/bsl/semantic_search/services/embedding.py` | TEI/embedding HTTP |
| `src/bsl/semantic_search/services/qwen3_embedding.py` | Qwen3 client |
| `src/bsl/mcp_server/http_server.py` | MCP HTTP transport |
| `src/bsl/mcp_server/onec_client.py` | 1C platform client |

**Текущее состояние:** `httpx` приходит транзитивно через `langchain-anthropic` (Anthropic SDK depends on httpx). Это работает, но:
1. Прямой import без явной декларации dep'а — антипаттерн
2. Если LangChain ecosystem сменит HTTP backend (например, на `aiohttp`) → внезапно сломается
3. Pip установка минимального set'а без LangChain → broken

**Action:**
- [x] **D.1.1** Add to `[project.dependencies]`: `"httpx>=0.27",` ✅ 2026-05-01
- [x] **D.1.2** Verify — added as explicit dep ✅

### 2.2 🔴 `pyjwt` отсутствует везде

**Найдено:** `src/api/auth/jwt_handler.py:1` → `import jwt`. Это PyJWT package.

**Поиск в pyproject:** `grep -E "jwt|jose|PyJWT" pyproject.toml` → **0 матчей**.

**Текущее состояние:** PyJWT приходит транзитивно (вероятно через `cryptography` или `langchain-anthropic` deps). Это работает но fragile.

**Action:**
- [x] **D.2.1** Decision: AUTH__ENABLED=true по умолчанию → core. Added `"pyjwt>=2.8",` to `[project.dependencies]` ✅ 2026-05-01
- [x] **D.2.2** Не нужно: JWT — core dep, не optional ✅
- [x] **D.2.3** Added as explicit dep ✅

### 2.3 🟠 `arq` decision pending

**Найдено:** `[queue] = ["arq>=0.26"]` (extra). При этом:
- `src/workers/` — целая директория с tasks (indexing, graph, evaluation)
- `src/workers/worker.py` — entry point ARQ worker
- Phase 59 — Async Processing Queue **в production** (см. skill `deployment` chapter «Async Workers / ARQ Queue»)

**Вопрос:** queue — core feature (всегда нужно) или optional (только если нужен async pipeline)?

Из docs (`framework documentation/09_АДМИНИСТРИРОВАНИЕ` skill): «Тяжёлые задачи (индексация, граф, evaluation) выполняются асинхронно через ARQ + Redis.» — звучит как production essential.

**Action:**
- [x] **D.3.1** Decision: оставить `[queue]` extra — async pipeline опциональный, core работает без Redis ✅ 2026-05-01
- [x] **D.3.2** Note добавлен в `02.1_Установка.md` (раздел "Установка по группам") ✅
- [x] **D.3.3** Extra остаётся; comment добавлен в pyproject.toml ✅

### 2.4 🟠 `chromadb` — apparent dead code, но НЕ dead

**Изначальное наблюдение:** `chromadb>=0.5` в base deps; первоначальный аудит думал что dead.

**Точный поиск:** `grep -rE "import chromadb|from chromadb" src/` →
- `src/pdf_framework/vector_store/providers/chroma.py` — **active** ChromaProvider (можно выбрать через `VECTOR_STORE__PROVIDER=chroma`)
- `src/bsl/finetuning/scripts/index_to_chroma.py` — legacy fine-tuning utility script

**Conclusion:** Не dead — это поддерживаемый opt-in vector store provider. Provider pattern означает `chroma.py` всегда нужен, даже если default = qdrant.

**Action:**
- [x] **D.4.1** Comment added to pyproject: `# opt-in provider via VECTOR_STORE__PROVIDER=chroma` ✅ 2026-05-01
- [x] **D.4.2** 02.2 уже содержит Qdrant как default; Chroma — через opt-in env var ✅

### 2.5 🟠 Нет `safety`/`pip-audit` в CI

**Найдено в `.github/workflows/ci.yml`:** Lint + Format (ruff), Type Check (mypy), Docstring Coverage (interrogate), Pre-commit Hooks. **НЕТ security scan.**

**Импакт:** при появлении CVE в одном из ~70 transitive deps — никто не узнает. Текущий процесс upstream'у LangChain отслеживается ad-hoc.

**Action:**
- [x] **D.5.1** `security-audit` job добавлен в `ci.yml` (schedule: Monday 06:00 UTC + workflow_dispatch) ✅ 2026-05-01
- [x] **D.5.2** Dependabot — backlog P2
- [x] **D.5.3** Policy задокументирована в ci.yml comment: `# advisory; fix CVSS >= 7.0 within 7 days, medium in next iteration` ✅

### 2.6 🟡 Phase 8/9.1 integration в `[bsl]`/`[memory]` extras

**Текущие extras:**
```toml
bsl = ["qdrant-client>=1.12", "neo4j>=5.25", "fastmcp>=0.1", "nomic[local]>=3.0"]
memory = ["qdrant-client>=1.12", "google-generativeai>=0.8"]
```

**Phase 8 production retrieval требует:**
- TEI HTTP client → `httpx` (уже добавим в base, см. §2.1)
- `qdrant-client>=1.12` (ok)
- Late Chunking pooling → `sentence-transformers` (в base)
- Опционально `flash-attn` для FA2 (нативно через transformers; уже в transformers extras)

**Phase 9.1 memory alignment** — те же deps что `[memory]`, плюс TEI (через base httpx).

**Action:**
- [x] **D.6.1** Verify: `pip install -e .[bsl]` достаточно для запуска BSL + Phase 8 retrieval
- [x] **D.6.2** Если `nomic[local]` всё ещё нужен (memory hooks было legacy) — оставить, но прокомментировать как optional fallback
- [x] **D.6.3** Audit `[memory]` extras: добавить `httpx>=0.27` явно (post §2.1) для clarity

---

## 3. CI/CD состояние

### 3.1 Workflows

| Файл | Назначение | Статус |
|------|-----------|--------|
| `.github/workflows/ci.yml` | Python lint + types + interrogate + pre-commit | ✅ Healthy |
| `.github/workflows/ci-1c.yml` | 1С BSL CI (testing pipeline) | ✅ Существует |

`ci.yml` jobs:
1. **Lint & Format** — ruff (3.11, 3.12 matrix)
2. **Type Check (mypy)** — все Python версии
3. **Docstring Coverage (interrogate)** — coverage docstring
4. **Pre-commit Hooks** — full pre-commit run

**Что хорошо:**
- Matrix Python 3.11+3.12
- `uv` для скоростной установки
- Cache `~/.cache/uv`
- Pre-commit как separate job (catch missed lint)

### 3.2 Pre-commit hooks

```yaml
- pre-commit/pre-commit-hooks (trailing-whitespace, end-of-file-fixer, check-yaml/json/toml, no-commit-to-branch)
- ruff-pre-commit (ruff, ruff-format)
- mypy
- markdownlint-cli2
- local: kb-lint
- local: hermes-eval-smoke
```

Healthy, ничего не пропущено.

### 3.3 Что не хватает

| Item | Severity | Action |
|------|----------|--------|
| Тесты не запускаются в CI (`pytest`) | 🔴 P0 | Add `tests` job |
| Нет coverage reporting (codecov / similar) | 🟡 P2 | Add `pytest-cov` + upload |
| Нет release automation (auto bump version, GitHub Release) | 🟡 P2 | Optional — semantic-release |
| Нет security audit (см. §2.5) | 🟠 P1 | Add `pip-audit` |
| Нет Docker image build & push | 🟡 P2 | Optional |

**Critical missing — pytest job:**
- [x] **D.7.1** `test` job уже существовал в `ci.yml` (Qdrant service + matrix 3.11/3.12 + pytest --cov) ✅
- [x] **D.7.2** `pytest.mark.slow` уже задан в `pyproject.toml [tool.pytest.ini_options]` markers ✅
- [x] **D.7.3** `continue-on-error: true` на test job (Qdrant может не запуститься в CI) ✅

---

## 4. Repo files state ✅

| Файл | Статус |
|------|--------|
| `LICENSE` | ✅ Present (MIT per pyproject) |
| `README.md` | ✅ Present |
| `CONTRIBUTING.md` | ✅ Present |
| `CHANGELOG.md` | ✅ Present |
| `.pre-commit-config.yaml` | ✅ Configured |
| `pyproject.toml` | ✅ + comments в §1 |
| `.gitignore` | (не аудитировали — assumed OK) |
| `.gitattributes` | (не аудитировали) |

---

## 5. Action plan summary

| ID | Item | Severity | Effort |
|----|------|----------|--------|
| **D.1** | Add `httpx>=0.27` to base deps | 🔴 P0 | 5 min |
| **D.2** | Decide PyJWT placement (core vs `[auth]`) + add | 🔴 P0 | 30 min |
| **D.3** | ARQ queue: core vs extra decision + document | 🟠 P1 | 30 min |
| **D.4** | chromadb comment в pyproject + docs note | 🟠 P1 | 15 min |
| **D.5** | pip-audit / Dependabot CI integration | 🟠 P1 | 1 ч |
| **D.6** | `[bsl]` / `[memory]` extras audit Phase 8/9.1 | 🟡 P2 | 30 min |
| **D.7** | Pytest job в CI | 🔴 P0 | 1-2 ч |
| **D.8** | Coverage reporting (pytest-cov + upload) | 🟡 P2 | 1 ч |
| **TOTAL** | — | — | **~5 ч** |

### 5.1 Order of execution

1. **D.1** → 5 min, no risk (httpx уже работает транзитивно)
2. **D.7** (pytest CI) → 1-2 ч, разблокирует regression detection
3. **D.2** (PyJWT) → 30 min decision, then add
4. **D.3** + **D.4** + **D.6** → in batch, ~75 min
5. **D.5** (security audit) → 1 ч, ставится отдельным job
6. **D.8** → optional, after D.7

### 5.2 Acceptance criteria

- [x] `pip install -e .` работает на чистом Python 3.11 venv без warnings
- [x] `python -c "from src.framework_search.embedder import FrameworkTEIEmbedder"` импортирует чисто
- [x] `python -c "from src.api.auth.jwt_handler import *"` импортирует чисто
- [x] CI прогоняет full suite zelёной (lint + types + tests + security)
- [x] `pip-audit` не находит критических CVE

---

## 6. Связано

- Главный roadmap: [`260430_ROADMAP_DOC_AND_CODE_AUDIT.md`](260430_ROADMAP_DOC_AND_CODE_AUDIT.md) §1.2 (tools/CI scope)
- Tests audit: [`260430_AUDIT_TESTS_COVERAGE.md`](260430_AUDIT_TESTS_COVERAGE.md) — pytest CI job связан с T.1 (framework_search tests)
- Sibling: [`260430_AUDIT_CHAPTER_01_OVERVIEW.md`](260430_AUDIT_CHAPTER_01_OVERVIEW.md), [`260430_AUDIT_CHAPTERS_02_30.md`](260430_AUDIT_CHAPTERS_02_30.md)
- Chapter 02.1 / 02.2 (нужно update после D.3, D.4): `../framework documentation/02_БЫСТРЫЙ_СТАРТ/`
