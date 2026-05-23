# Roadmap 260519 — Иерархичная code-anchored документация PDF Framework

**Дата:** 2026-05-19 (создан) → 2026-05-19 (intermediate update §11-12)
**Статус:** proposed → **paused for review** (см. §11 интермейт findings, §12 открытые вопросы)
**Cross-ref research:** [hierarchical-code-anchored-docs-2026.md](../../.claude/skills/architecture-research/cache/hierarchical-code-anchored-docs-2026.md)
**Связано:**
- [docs-change-enforcer.py](../../.claude/hooks/docs-change-enforcer.py) `CODE_TO_DOMAIN` (строки 70-156)
- skill [`audit-docs`](../../.claude/skills/audit-docs/SKILL.md)
- [00_СОДЕРЖАНИЕ.md](../framework%20documentation/00_СОДЕРЖАНИЕ.md) — 37 глав
- [260515_ROADMAP_AUTO_COVERAGE_AUDIT.md](260515_ROADMAP_AUTO_COVERAGE_AUDIT.md) — Phase A/B/C gaps

## §1. Цель

Дать инструмент, который **автоматически генерирует точную иерархичную документацию из текущего кода** — иными словами, закрыть три проблемы:

1. **Drift code↔docs.** Сегодня документация пишется руками; `docs-change-enforcer` лишь сигналит «надо обновить главу X», но не **что именно** обновить.
2. **Нет API reference.** 37 глав описывают концепции и архитектуру, но не содержат канонической документации функций/классов из `src/pdf_framework/`. Когда новый разработчик хочет узнать сигнатуру `HybridSearch.search()` — он читает исходник.
3. **Decomposition не машиночитаемый.** `CODE_TO_DOMAIN` — список из 87 строк в Python. Нужен формальный реестр подсистем с метаданными (owner, status, dependencies, doc-coverage %).

Целевое состояние:
- `mkdocs serve` поднимает локальный сайт по 37 главам + auto-API reference по `src/`.
- При каждом push в feature-branch CI обновляет API reference, проверяет drift, генерирует C4-диаграммы.
- Полный обход GitHub UI-лимита 300 файлов для review — site становится альтернативной точкой review (per-chapter changelog + per-symbol changelog).

## §2. Tool survey (subset из cache, отфильтровано под наш контекст)

Полный обзор — в [cache](../../.claude/skills/architecture-research/cache/hierarchical-code-anchored-docs-2026.md). Ниже только то, что подходит **именно нашему стеку** (Python 3.11+, MD-first, Mermaid, существующие 37 глав).

### 2.1 Site generator

**Решение: MkDocs Material** ([squidfunk/mkdocs-material](https://github.com/squidfunk/mkdocs-material), 21k⭐).

| Критерий | MkDocs Material | Docusaurus | Sphinx | Backstage TechDocs |
|---|---|---|---|---|
| Markdown-first | ✓ | MDX | RST (MD через myst-parser) | ✓ |
| Python stack | ✓ | Node.js | ✓ | Node.js |
| Mermaid native | ✓ | ✓ | через ext | через plugin |
| Существующие 37 MD-файлов | drop-in | drop-in | требует RST или myst | требует service-catalog |
| Время до first preview | <30 мин | ~1 час | ~2 часа | ~1 день |
| **Решение для нас** | **YES** | overhead Node | overhead RST | overhead infra |

**Caveat:** Material for MkDocs вошёл в maintenance mode в Q1 2026; Zensical — успешник для greenfield. Для нас (brownfield, 37 глав MD уже есть) maintenance mode — ОК, миграция не оправдана. См. [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/).

### 2.2 API reference

**Решение: mkdocstrings + mkdocstrings-python** ([mkdocstrings/mkdocstrings](https://github.com/mkdocstrings/mkdocstrings), 1.8k⭐).

Почему:
- Recursive — `::: src.pdf_framework.search` авто-генерирует все классы/функции рекурсивно по dotted-path.
- Поддерживает Google/Numpy/Sphinx docstring-стили (у нас Google-style уже).
- Cross-ref: `[HybridSearch][src.pdf_framework.search.hybrid_search.HybridSearch]` — авто-резолвит.
- Авто-TOC в Material navigation.

Альтернативы: `sphinx-autoapi` (требует Sphinx), `pdoc` (минималистичный, не интегрируется с MkDocs).

### 2.3 Architecture diagrams

**Решение: Mermaid (built-in) + опционально PyStructurizr для C4** (опционально на Фазе 3+).

Анализ trade-off:
- **Mermaid** уже используется в наших docs, рендерится на GitHub и в MkDocs Material. Минус — нет single-source-of-truth: если рисуем Container view + Component view одной системы, дублируем имена.
- **Structurizr DSL** — single model → multiple views, но требует `structurizr-cli` (Java) или `structurizr-lite` Docker для рендера, отдельный workflow.
- **PyStructurizr** ([nielsvanspauwen/pystructurizr](https://github.com/nielsvanspauwen/pystructurizr)) — Python DSL, генерирует .puml/.dsl на выходе.

Рекомендация: **Mermaid для Фазы 0-2, PyStructurizr вводим на Фазе 3 если drift между views станет проблемой**.

Источники: [A comparison of C4 tooling](https://optimalrelations.se/blog/comparison-c4-tooling), [Simon Brown — Software architecture diagrams](https://dev.to/simonbrown/software-architecture-diagrams-which-tool-should-we-use-29e).

### 2.4 Drift detection

**Решение: гибрид существующий `docs-change-enforcer` + новый `mkdocs-include-markdown` + опционально Vale**.

- **Существующий `CODE_TO_DOMAIN`** — оставляем, расширяем до структурированного YAML (см. §3.2).
- **`mkdocs-include-markdown-plugin`** ([mondeja/mkdocs-include-markdown-plugin](https://github.com/mondeja/mkdocs-include-markdown-plugin)) — позволяет инжектить **реальные** code-snippets из исходника в MD. Snippet меняется в коде → автоматически в docs. Single-source-of-truth.
- **Vale** ([errata-ai/vale](https://github.com/errata-ai/vale), 4.5k⭐) — prose-linter с кастомными правилами (терминология, стиль, запрет vague-фраз вроде "очень быстро"). На Фазе 4.
- **markdown-link-check** ([tcort/markdown-link-check](https://github.com/tcort/markdown-link-check)) — broken-link CI gate. На Фазе 1.

**Swimm** ([G2 Reviews 2026](https://www.g2.com/products/swimm/reviews)) — patented Auto-sync для code-coupled docs; коммерческий продукт. Не берём (vendor lock-in + privacy для BSL кода), но архитектурно подсматриваем idea: "docs are tests".

### 2.5 Methodology

**Решение: Diátaxis** ([diataxis.fr](https://diataxis.fr/)) как классификация страниц + **arc42** для шапок глав уровня "архитектура подсистемы".

Diátaxis 4 типа:
1. **Tutorial** — обучение (одна задача от начала до конца). У нас: `02_БЫСТРЫЙ_СТАРТ`.
2. **How-to** — рецепт для конкретной задачи. У нас: `10_УСТРАНЕНИЕ_НЕПОЛАДОК`.
3. **Reference** — API/CLI справочник (читается как словарь). У нас: пока нет → закрывается через mkdocstrings.
4. **Explanation** — концептуальные объяснения "почему так". У нас: большинство глав.

Каждая страница помечается one-of-4 типом в frontmatter:

```yaml
---
title: "04.9 Matryoshka Embeddings"
diataxis: explanation
arc42_section: building_block_view
owner: alex
status: stable | draft | deprecated
code_refs:
  - src/framework_search/indexer.py
  - scripts/matryoshka_*.py
related_skills: [embedding-models, qdrant-operations]
last_verified: 2026-05-17
---
```

Это даст **machine-readable** субсистемный реестр, по которому MkDocs nav + drift-checker строят отчёты.

## §3. Recommended stack

```
┌─────────────────────────────────────────────────────────┐
│ docs.example.local  (MkDocs Material, локально + CI)    │
├─────────────────────────────────────────────────────────┤
│  Navigation:                                            │
│   - 01_ОБЗОР … 37_HERMES_LLM_WIKI  (existing MD)        │
│   - API Reference                  (mkdocstrings auto)  │
│   - Roadmaps                       (docs/roadmap/*.md)  │
│   - ADRs                           (.claude/skills/.../adr/)│
├─────────────────────────────────────────────────────────┤
│  Plugins:                                               │
│   - mkdocstrings[python]   ← API reference из src/      │
│   - include-markdown       ← реальные code-snippets     │
│   - mermaid2 / native      ← диаграммы                  │
│   - awesome-pages          ← nav без правки mkdocs.yml  │
│   - git-revision-date      ← last-updated badge         │
│   - tags                   ← cross-cutting навигация    │
├─────────────────────────────────────────────────────────┤
│  CI gates (.github/workflows/docs.yml):                 │
│   - markdown-link-check   ← broken links FAIL build     │
│   - mkdocs build --strict ← warnings FAIL build         │
│   - subsystems-registry-validator  (наш custom)         │
│   - Vale (Фаза 4)         ← prose linter                │
├─────────────────────────────────────────────────────────┤
│  Источник истины:                                       │
│   - subsystems.yaml      ← реестр 37+ подсистем         │
│   - src/**/*.py          ← код + docstrings             │
│   - docs/**/*.md         ← объяснения + tutorial        │
│   - .claude/skills/      ← workflow-knowledge           │
└─────────────────────────────────────────────────────────┘
```

### 3.1 Зависимости (Python deps)

```toml
# pyproject.toml [project.optional-dependencies.docs]
docs = [
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.5.0",
    "mkdocstrings[python]>=0.27.0",
    "mkdocs-include-markdown-plugin>=7.0.0",
    "mkdocs-awesome-pages-plugin>=2.9.0",
    "mkdocs-git-revision-date-localized-plugin>=1.2.0",
    "mkdocs-mermaid2-plugin>=1.1.0",
]
```

### 3.2 `subsystems.yaml` — machine-readable реестр

Заменяет неявный `CODE_TO_DOMAIN` Python-список на explicit YAML, который читают одновременно:
- MkDocs nav generator (`scripts/build_docs_nav.py`)
- `docs-change-enforcer.py` (вместо hardcoded списка)
- `audit-docs` skill
- GitHub-side review tooling (filter PR files by subsystem)

```yaml
# docs/subsystems.yaml
version: 1
subsystems:
  - id: "03_indexing"
    chapter: "03_ИНДЕКСАЦИЯ"
    title: "PDF Indexing"
    diataxis: explanation
    status: stable
    owner: alex
    skills: [indexing-pipeline, graph-operations]
    code_paths:
      - src/pdf_framework/loaders/
      - src/pdf_framework/processing/
      - src/pdf_framework/indexing/
    overrides:  # specific files that escape general prefix
      - path: src/pdf_framework/indexing/wiki_exporter.py
        chapter: "32_WIKI_KNOWLEDGE_LAYER"
        skills: [wiki-pipeline]
    dependencies: [02_quickstart, 04_search]
    last_verified: "2026-05-19"

  - id: "31_qwen3"
    chapter: "31_QWEN3_RETRIEVAL_PRODUCTION"
    title: "Qwen3 Embedding Retrieval Production"
    diataxis: reference
    status: stable
    skills: [framework-search, embedding-models]
    code_paths:
      - src/framework_search/
      - scripts/reindex_*.py
      - scripts/matryoshka_*.py
    dependencies: [02_quickstart, 03_indexing, 04_search]
    last_verified: "2026-04-30"
```

### 3.3 Predicted layout `mkdocs.yml`

```yaml
site_name: PDF Vector & Graph Framework
nav:
  - Обзор: 01_ОБЗОР/index.md
  - Быстрый старт: 02_БЫСТРЫЙ_СТАРТ/index.md
  - Подсистемы:
      - Индексация: 03_ИНДЕКСАЦИЯ/index.md
      - Поиск: 04_ПОИСК/index.md
      - RAG Агенты: 05_RAG_АГЕНТЫ/index.md
      # ... 37 глав
  - API Reference:
      - src.pdf_framework: api/pdf_framework.md  # ::: src.pdf_framework
      - src.framework_search: api/framework_search.md
      - src.memory: api/memory.md
      - src.bsl: api/bsl.md
  - Roadmaps:
      - 2026-05: roadmap/2026-05.md
  - ADRs:
      - Architecture: adr/index.md

plugins:
  - search
  - awesome-pages          # auto-discover, no nav micromanagement
  - mkdocstrings:
      handlers:
        python:
          paths: [src]
          options:
            docstring_style: google
            show_source: true
            members_order: source
  - include-markdown
  - git-revision-date-localized
  - mermaid2

theme:
  name: material
  features: [content.code.copy, navigation.tracking, navigation.tabs, navigation.indexes]
```

## §4. Закрытие doc-gaps (главы 38-41)

Из предыдущего анализа PR определены 4 подсистемы, реализованные в коде, но не имеющие выделенных глав. Решение: **создать stub-главы**, не дробить существующие.

| № | Title | Code paths | Связанные skills | Rationale |
|---|---|---|---|---|
| **38_INFRA_PIPELINE** | Docker stacks, Prefect workers, CI/CD | `infra/`, `docker/`, `.github/workflows/`, `scripts/git_hooks/` | `deployment`, `claude-code-github-actions` | 6 docker-compose, 3 workflow YAML, 5 git-hooks — не описано как subsystem |
| **39_MATRYOSHKA_OPTIMIZATION** | MRL truncation + SQ int8 alias-swap | `scripts/matryoshka_*.py`, `src/framework_search/indexer.py` helpers | `framework-search`, `qdrant-operations` | 7 scripts + alias-swap pattern; раздел в 04.9 уже перегружен |
| **40_BENCHMARKING** | bench_* scripts + eval datasets | `scripts/bench_*.py`, `data/eval/`, `tests/benchmarks/` | `evaluation-benchmark` | 6 bench scripts, golden_v* datasets — pipeline регресс-тестов |
| **41_SCHEMAS_CONTRACTS** | Pydantic schemas, link-registry, migrations | `src/pdf_framework/schemas/`, `migrations/`, `scripts/migrate_link_registry.py` | `framework-config` | Контракты данных + SQL миграции в одном месте |

Stub-формат (минимальный):

```markdown
---
title: "38 Инфраструктура и Pipeline"
diataxis: explanation
arc42_section: deployment_view
status: stub
code_refs:
  - infra/pipeline/
  - docker/
  - .github/workflows/
related_skills: [deployment]
last_verified: 2026-05-19
---

# 38. Инфраструктура и Pipeline

> **STUB.** Глава выделена 2026-05-19 для зеркалирования код-подсистемы.
> Полное наполнение — в roadmap 260519 §5 Фаза 1.

## Что входит
[пункт + ссылка на каталог]

## Связи
[ссылки на главы 09, 30]

## API Reference
::: src.api.dependencies
    options:
      members_order: source
```

## §5. Phase plan

### Phase 0 — Bootstrap (1 день)

- [ ] Установить deps в `pyproject.toml [optional-dependencies.docs]`
- [ ] Создать минимальный `mkdocs.yml` с навом на 37 существующих глав
- [ ] `mkdocs serve` локально — убедиться что все 37 рендерятся
- [ ] Добавить в `.gitignore` `site/` (output mkdocs build)
- [ ] Документировать в `09_АДМИНИСТРИРОВАНИЕ/` под-главу "Документация фреймворка"

**Exit criteria:** `mkdocs serve` поднимается, видны все 37 глав, поиск работает.

### Phase 1 — API Reference + Link checks (2 дня)

- [ ] Подключить `mkdocstrings[python]` с `paths: [src]`
- [ ] Создать `docs/api/` с автогенерируемыми reference-страницами для 4 топ-модулей: `pdf_framework`, `framework_search`, `memory`, `bsl`
- [ ] Проверить покрытие docstrings (`pydocstyle` или `interrogate`); добить < 80% covered модули
- [ ] CI workflow `.github/workflows/docs.yml`: `mkdocs build --strict` + `markdown-link-check` на изменённых файлах
- [ ] Cross-ref паттерн в существующих главах: `[HybridSearch][src.pdf_framework.search.hybrid_search.HybridSearch]`

**Exit criteria:** `/api/` доступно, `mkdocs build --strict` зелёный, broken links блокируют PR.

### Phase 2 — Subsystem registry (1 день)

- [ ] Создать `docs/subsystems.yaml` из текущего `CODE_TO_DOMAIN`
- [ ] Скрипт `scripts/sync_code_to_domain.py`: читает YAML → генерит Python-список для `docs-change-enforcer.py`
- [ ] `scripts/validate_subsystems.py`: проверяет (a) каждый chapter существует, (b) каждый code_path существует, (c) каждый skill есть в `.claude/skills/`
- [ ] Hook `pre-commit` запускает validate_subsystems при изменении `subsystems.yaml`
- [ ] Создать stub-главы 38-41 (см. §4) с placeholder контентом

**Exit criteria:** `docs-change-enforcer` читает YAML вместо hardcoded; phantom-skills/paths падают при validate.

### Phase 3 — Diagrams + include-markdown (2 дня)

- [ ] Подключить `mkdocs-include-markdown-plugin` для snippets-from-source
- [ ] Конвертировать 5 наиболее часто-меняющихся code-snippets в существующих главах из inline → include (single-source-of-truth)
- [ ] Создать `docs/diagrams/` с Mermaid C4 Context + Container view для каждой из 8 review-кластеров
- [ ] (опционально) Eval PyStructurizr для главного C4 model

**Exit criteria:** изменение кода в `src/api/dependencies/Components.__init__` автоматически отражается в 06.4_MCP_Server.md без правки MD; 8 C4 диаграмм в docs.

### Phase 4 — Drift gate + prose linter (2 дня)

- [ ] Расширить `docs-change-enforcer` использованием `subsystems.yaml`; добавить **inverse check**: при `git diff` файла из `code_paths` подсистемы X — проверить что `mtime` главы X старше mtime изменённого кода → warn
- [ ] Установить Vale с базовыми правилами (терминология BSL/1С, запрет vague "очень быстро"/"эффективно", consistency English-Russian для тех. терминов)
- [ ] CI gate: Vale на изменённых MD-файлах
- [ ] Добавить `last_verified` enforcement: если frontmatter older than 6 months — warn

**Exit criteria:** docs CI блокирует merge при code-without-doc-touch или stale-frontmatter.

### Phase 5 — GitHub Pages publish + scoped review UI (1 день)

- [ ] CI publish на `gh-pages` branch (или `mkdocs-material` deploy command)
- [ ] Каждый PR деплоит preview через GitHub Pages preview (через `mkdocs-publisher` или ручной workflow)
- [ ] Документировать в roadmap "scoped review tip": используй PR preview доку для review больших PR (обход 300-file limit)

**Exit criteria:** опубликованный сайт; alternate review pathway для PRs >300 files.

### Phase 6 — Backstage TechDocs (опционально, далеко)

Только если команда вырастет до 5+ человек и потребуется service catalog с per-team ownership. До этого — overkill. Источник: [backstage/backstage](https://github.com/backstage/backstage).

## §6. Метрики успеха

| Метрика | Baseline (2026-05-19) | Target Phase 2 | Target Phase 4 |
|---|---|---|---|
| Покрытие подсистем главами docs | 33/37+4 = 80% | 41/41 = 100% | 41/41 |
| Docstring coverage (interrogate) | ~50% (estimate) | 70% | 90% |
| Broken links в `docs/` | unknown | 0 (CI gate) | 0 |
| Время до first preview новичка | ~неизмеримо | <30 мин (`mkdocs serve`) | <10 мин |
| Drift incidents/month (по docs-change-enforcer todos) | ~10 | <5 | <2 |
| % MD-файлов с frontmatter | ~5% | 100% | 100% |

## §7. Решения которые НЕ принимаем

- **Backstage** — overkill для команды <5 человек; вернёмся на Фазе 6 если масштаб вырастет.
- **Swimm** — vendor lock-in + privacy для BSL/конфигурации 1С. Архитектурную idea "docs are tests" реализуем через include-markdown + frontmatter validation.
- **Sphinx** — требует RST или myst-parser; ломает существующий MD-pipeline; единственное преимущество (`sphinx-autoapi`) перекрывает mkdocstrings.
- **Docusaurus / Astro Starlight** — добавляют Node.js stack; команда работает в Python.
- **Полный rewrite 37 глав** под Diátaxis — слишком инвазивно. Применяем классификацию через frontmatter без перестройки контента.

## §8. Открытые вопросы

1. **`docs/wiki/` (3 121 файл)** — auto-generated entities из graph. Включать в MkDocs nav или оставить отдельным сайтом? Предложение: отдельный sub-site `wiki.example.local`, главная docs ссылается.
2. **Главы 38-41** — создаём как stubs (см. §4) или интегрируем как разделы существующих глав? Предложение: stubs (явная subsystem-границы машинно-читаемы).
3. **PyStructurizr vs Mermaid C4** — экспериментировать на Фазе 3 или отложить? Предложение: Mermaid сейчас, evaluate PyStructurizr только если drift между container/component views станет проблемой.
4. **Скорость builds** — 37 глав × 4 топ-модулей API могут давать `mkdocs build` >30s. Если >60s — рассмотреть `mkdocs-build-plantuml-plugin` cache или partial builds.

## §9. Risk register

| Риск | Вероятность | Митигация |
|---|---|---|
| Material for MkDocs maintenance mode → bugs не фиксятся | Low | Версии стабильные >2 года, fallback на Zensical через 1-2 года |
| Docstring coverage <50% → API reference scarce | Medium | Phase 1 включает campaign по поднятию coverage |
| `subsystems.yaml` дрейфует от `CODE_TO_DOMAIN` | Medium | Phase 2: single source of truth = YAML, генерим Python из него |
| Cyrillic в filenames ломает mkdocs URL | Medium | Тестируем на Phase 0; fallback — slug-rewrites через `awesome-pages` |
| Команда не ведёт frontmatter | High | Phase 4 enforcement + примеры в каждой главе |

## §10. Следующий шаг

После approval roadmap'а:
1. Запустить Phase 0 (1 день) — proof-of-concept на текущих 37 главах.
2. После Phase 0 — review результата, корректировка плана Phase 1-5.
3. Параллельно — финализировать stub-главы 38-41 (отдельный коммит).

---

## §11. Intermediate findings (2026-05-19, code audit ревизия §4)

> **Контекст обновления.** §4 первоначально предложил 4 новые главы (38-41) на базе `CODE_TO_DOMAIN` mapping. После прямого аудита `src/`, `tools/`, `infra/`, `scripts/` выяснилось: mapping консервативен (создавался для drift-detection, не subsystem-discovery) — gap'ов больше.

### 11.1 Что аудитировал

Прямой `ls`/`find` по:
- `src/` (10 top-level subfolders) + `src/pdf_framework/` (24 subfolders)
- `src/bsl/` (11 framework-subsystems помимо 1С metadata-папок)
- `tools/` (15+ инструментов помимо node_modules)
- `infra/` (4 верхних: docker-mcp, lazy-mcp, pipeline, task-master)
- `scripts/` (~120 скриптов)
- `migrations/` (2 SQL)

### 11.2 Карта gap'ов (после аудита)

🔴 **Zero coverage — требуют отдельной главы**:

| Подсистема | Файлов | Размер | Diátaxis verdict |
|---|---|---|---|
| `src/bsl/finetuning/` (Colab notebooks + train scripts) | 5+ | substantial | **YES** — standalone read-path "как обучить embedding на BSL" |
| `tools/sonar-*.jar` + `src/bsl/sonar/` + `sonar-project.properties` | ~10 | substantial | **YES** — standalone "как настроить SonarQube для BSL" |
| `infra/task-master/` + task-master-ai MCP | ? | TBD (требуется измерить) | **PENDING** |

🟡 **Группировочные главы — связные tools без единой обзорной точки**:

| Группа | Tools | Текущее покрытие |
|---|---|---|
| **BSL Toolchain Ecosystem** | bsl-ls (LSP), ast-grep-mcp, multilspy-fork, auto-documenter, bsl-semantic-diff, mcp-reasoner, 1c-docs-rag, coverage41c, serena | scattered mentions в 28, 17, 36 — нет обзорной главы |

🟢 **Малые подсистемы — sub-разделы существующих глав**:

| Подсистема | LOC/файлов | Куда |
|---|---|---|
| `src/pdf_framework/analytics/` (audit/cost/tracker) | 3 файла | sub 09 (новый 09.15_Analytics.md) |
| `src/pdf_framework/chains/qa/` | small | sub 05 |
| `src/pdf_framework/tools/` (document/graph_query/retrieval) | small | sub 05 |
| `src/pdf_framework/quick.py` (QuickRAG API) | 226 LOC | sub 06 (новый 06.X_QuickRAG.md) |
| `src/bsl/call_graph/` (2) + `src/bsl/knowledge_graph/` (2) + `src/bsl/parser/` (5) + `coding_assistant/` (2) + `evaluation/` (2) | mostly 2-5 files | sub 28 |

### 11.3 Почему §4 был консервативен

`CODE_TO_DOMAIN` в `docs-change-enforcer.py` — это **drift-detection mapping**, не **subsystem catalog**. Его SKIP_PATTERNS исключают целиком:
- `src/bsl/` (как «not framework code») → пропускает framework-функционал `finetuning/`
- `tools/` (как «infrastructure») → пропускает 9 user-facing tools
- `scripts/` (как «utility») → пропускает группу `bench_*`, `finetune_*`, `matryoshka_*`

Lesson: при следующем audit использовать **прямой `ls src/ tools/ infra/`**, не полагаться на existing mapping.

### 11.4 Diátaxis 2-of-3 методология (новая)

Главу выделяем если ответ «да» на **2 из 3**:
1. **Standalone read-path** — пользователь приходит читать ТОЛЬКО эту главу с конкретной задачей? (Diátaxis: discoverability)
2. **Owner boundary** — единый owner или skill? (Diátaxis: maintainability)
3. **Internal structure** — минимум 3 подраздела (.1, .2, .3)? (Diátaxis: depth)

Прогон кандидатов:

| Глава | Standalone? | Owner? | ≥3 sub? | Verdict |
|---|---|---|---|---|
| 38_INFRA_PIPELINE | ✓ | ✓ deployment | ✓ docker/CI/git-hooks | **YES** |
| 39_MATRYOSHKA | ✓ | ✓ framework-search | ✓ MRL/SQ/alias-swap | **YES** |
| 40_BENCHMARKING | ✓ | ✓ evaluation-benchmark | ✓ bench/eval/golden | **YES** |
| 41_SCHEMAS_CONTRACTS | ✓ | ✓ framework-config | ✓ pydantic/migrations/registry | **YES** |
| **42_BSL_FINETUNING** | ✓ | ✓ embedding-models | ✓ dataset/train/eval | **YES** |
| **43_SONAR_QUALITY_GATE** | ✓ | ✓ | ✓ config/scan/rules | **YES** |
| **45_BSL_TOOLCHAIN_ECOSYSTEM** | ✓ | shared | ✓ LSP/AST/semantic-diff | **YES** (обзорная) |
| 44_TASK_MASTER (cand.) | ? | ? | ? | **PENDING** size check |
| 46_CALL_GRAPH | ✗ часть 28 | ✗ | ✗ | **NO** → sub 28 |
| 47_ANALYTICS | ✗ часть 09 | ✗ | ✗ | **NO** → sub 09.15 |

### 11.5 Обновлённая декомпозиция (replaces §4)

Три варианта:

| Вариант | Новые главы | Trade-off |
|---|---|---|
| **A. Консервативный (4)** | 38, 39, 40, 41 | Закрывает только zero-coverage в коде; finetuning + sonar + tools остаются сиротами |
| **B. Балансный (7)** ← **рекомендую** | 38, 39, 40, 41, **42_BSL_FINETUNING**, **43_SONAR_QUALITY_GATE**, **45_BSL_TOOLCHAIN_ECOSYSTEM** | Закрывает все 🔴 + единая точка для 9 BSL-tools |
| **C. Балансный + TaskMaster (8)** | B + **44_TASK_MASTER_AUTOMATION** | Решение после size-check `infra/task-master/` |
| **D. Максималистский (11+)** | C + 46_CALL_GRAPH + 47_ANALYTICS + 48_COVERAGE_QUALITY | Над-фрагментация — нарушает Diátaxis principle |

### 11.6 Stub-формат для глав 42-45 (расширяет §4)

42_BSL_FINETUNING:
```markdown
---
title: "42 Fine-tuning Qwen3 на BSL"
diataxis: how-to
status: stub
code_refs:
  - src/bsl/finetuning/
  - scripts/finetune_qwen3_bsl_mrl.py
  - scripts/collect_bsl_finetune_pairs.py
related_skills: [embedding-models, bsl-semantic-search]
last_verified: 2026-05-19
---

# 42. Fine-tuning Qwen3 на BSL

## 42.1 Dataset preparation (collect_bsl_finetune_pairs.py)
## 42.2 Training (notebooks/BSL_Finetuning_Colab.ipynb)
## 42.3 MRL-aware fine-tune (finetune_qwen3_bsl_mrl.py)
## 42.4 Eval против baseline (см. главу 40)
```

43_SONAR_QUALITY_GATE:
```markdown
---
title: "43 SonarQube Quality Gate (BSL + Python)"
diataxis: how-to
code_refs:
  - tools/sonar-bsl-plugin.jar
  - tools/sonar-scanner-6.2.1.4610-windows-x64/
  - src/bsl/sonar/
  - sonar-project.properties
related_skills: [deployment]
---

# 43. SonarQube Quality Gate

## 43.1 Установка sonar-bsl-plugin
## 43.2 sonar-project.properties и CLI запуск
## 43.3 Custom rules для BSL (rules_manager.py)
## 43.4 CI integration (.github/workflows)
```

45_BSL_TOOLCHAIN_ECOSYSTEM (обзорная):
```markdown
---
title: "45 BSL Toolchain Ecosystem"
diataxis: reference
code_refs:
  - tools/bsl-ls/
  - tools/ast-grep-mcp/
  - tools/multilspy-fork/
  - tools/auto-documenter/
  - tools/bsl-semantic-diff/
  - tools/mcp-reasoner/
  - tools/1c-docs-rag/
  - tools/coverage41c/
  - tools/serena/
related_skills: [bsl-development, bsl-refactoring-workflow]
---

# 45. BSL Toolchain Ecosystem

## 45.1 Decision Matrix — какой tool для какой задачи
## 45.2 LSP layer (bsl-ls, multilspy-fork)
## 45.3 AST tools (ast-grep-mcp, bsl-semantic-diff)
## 45.4 Code documentation (auto-documenter)
## 45.5 Coverage (coverage41c)
## 45.6 Reasoning (mcp-reasoner, serena)
## 45.7 1C-specific docs (1c-docs-rag)
```

## §12. Открытые вопросы для возврата

При продолжении (когда вернёмся):

1. **Approval варианта B / C / D.** Сейчас рекомендую B (7 глав). Если task-master объёмный — C (8 глав).
2. **Size check `infra/task-master/`** — нужно измерить, прежде чем коммитить 44.
3. **Расщеплять ли 28_BSL_SEMANTIC_SEARCH?** В нём уже 5 подразделов; добавление sub-глав для call_graph/parser/coding_assistant даст 8+ — может быть пересмотрено как 28 + 28a + 28b или просто оставить как есть.
4. **Расщеплять ли 09_АДМИНИСТРИРОВАНИЕ?** Сейчас 14 подразделов (09.1-09.14); добавление 09.15_Analytics приведёт к 15. Возможный split: 09_DEPLOYMENT (docker/rate-limit/auth) + 09a_OBSERVABILITY (langfuse/prometheus/monitoring) + 09b_HOOKS_AUTOMATION (auto-git-save, skill-enforcement).
5. **stub-главы — placeholder теперь или заполнять сразу?** Текущий план §4 → создать stub, наполнять в Phase 1. Альтернатива — наполнять сразу при создании.
6. **`docs/wiki/` подсистема** (3 121 файлов auto-generated) — отдельный sub-site `wiki.example.local` (§8 q1) — нужно решение прежде чем стартует Phase 0.
7. **Когда стартует Phase 0?** Зависит от решения по варианту глав + другие приоритеты (PR review, debug-hmr Phase 2, etc.).

### Триггеры возврата к roadmap

Вернуться к этому roadmap если:
- User says "продолжаем roadmap 260519" / "пора делать docs site"
- Завершён PR review (260519 disjoint master) — освобождает context для tooling work
- Появится новая подсистема в коде без главы (audit-via-`docs-change-enforcer` UNMAPPED)
- Phase 8 Qwen3 будет полностью stable (не нужно частить documentation pages)

---

**Подпись:** Claude Opus 4.7 + research cache [hierarchical-code-anchored-docs-2026.md](../../.claude/skills/architecture-research/cache/hierarchical-code-anchored-docs-2026.md)

**Changelog:**
- 2026-05-19 initial proposal (§1-10): MkDocs stack + 4 новые главы (38-41) + 6-фазный план
- 2026-05-19 intermediate update (§11-12): direct code audit ревизия — обнаружены 3 zero-coverage gap'а (finetuning, sonar, BSL toolchain) + Diátaxis 2-of-3 методология + 7 open questions для следующей сессии
