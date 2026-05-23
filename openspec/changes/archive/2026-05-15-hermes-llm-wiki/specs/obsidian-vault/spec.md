# Spec: obsidian-vault

**Change:** hermes-llm-wiki
**Phase:** 1
**Profile:** python-framework

## Контекст

У фреймворка уже есть **прото-wiki** в виде 8 файлов в `docs/architecture/` (`overview.md`, `triad-architecture.md`, `ralph-wiggum.md`, `hooks-reference.md`, `skills-reference.md`, `PATTERNS.md`, `bsl-integration.md`, `core-framework-separation.md`), 11+ cache-директорий в `.claude/skills/*/cache/`, и `docs/roadmap/*.md`. Но они не связаны `[[wiki-links]]`, не имеют frontmatter, и нет централизованной навигации.

Obsidian desktop + плагин Local REST API + MCP-сервер `mcp-obsidian` (3.3k⭐, Python, MIT) позволяют превратить эти разрозненные файлы в **единый vault** с graph view, backlinks и семантическим поиском — без переписывания существующих документов, только через добавление frontmatter и wiki-links.

Важное ограничение: `memory/MEMORY.md` (user-level Claude Code auto-memory) находится по пути `C:\Users\AlexT\.claude\projects\D--1--Framework\memory\` — **не в git**, не в project root. Решено (v1.3.4): vault root = project root, **без** user-level memory/, она остаётся отдельным user context.

---

## ## ADDED REQ-1: obsidian-mcp MCP server integration

**Файл:** `.mcp.json`

Добавление `obsidian-mcp` сервера (`MarkusPfundstein/mcp-obsidian`, Python, MIT, 3.3k stars) с env-переменными для подключения к локальному Obsidian через Local REST API плагин.

### Конфигурация

```json
{
  "mcpServers": {
    "obsidian-mcp": {
      "command": "python",
      "args": ["-m", "mcp_obsidian"],
      "env": {
        "OBSIDIAN_API_KEY": "${OBSIDIAN_API_KEY}",
        "OBSIDIAN_HOST": "127.0.0.1",
        "OBSIDIAN_PORT": "27123",
        "OBSIDIAN_VAULT_PATH": "D:/1С-Framework"
      }
    }
  }
}
```

### Tools предоставляемые mcp-obsidian (7 шт.)

- `list_files_in_vault(path: str)` — список файлов в vault path
- `get_file_contents(path: str)` — чтение файла
- `search(query: str)` — Obsidian full-text search
- `patch_content(path: str, operation: str, content: str)` — patch по frontmatter/heading/block reference
- `append_content(path: str, content: str)` — append к файлу
- `delete_file(path: str)` — удаление
- `batch_get_file_contents(paths: list[str])` — batch чтение

### Сценарий 1: Проверка доступности

**Given** Obsidian desktop запущен с Local REST API плагином на порту 27123
**And** `OBSIDIAN_API_KEY` установлен в env
**When** Claude Code запускается и `.mcp.json` парсится
**Then** `obsidian-mcp` сервер стартует успешно
**And** `list_files_in_vault("/")` возвращает non-empty list (минимум существующие docs/)
**And** `search("framework")` возвращает релевантные matches из docs/architecture/

### Сценарий 2: Graceful degradation

**Given** Obsidian desktop не запущен
**When** `WikiSearchAdapter.search(query)` (из Phase 0) вызывается
**Then** adapter ловит connection error
**And** возвращает пустой список с log warning `[WIKI-ADAPTER] Obsidian not available`
**And** `unified_search` продолжает работу с другими адаптерами (fallback на L1-L3)

### Граничные условия

- `OBSIDIAN_API_KEY` не установлен → MCP server стартует, но первый запрос возвращает 401 → обёртка в CircuitBreaker (Phase 0)
- Obsidian port занят другим процессом → в instruction'е к настройке указать изменение порта
- Vault path содержит кириллицу (`1С-Framework`) → Windows-specific, проверить что mcp-obsidian корректно обрабатывает (может потребоваться POSIX-style `/c/...` или URL encoding)
- Размер vault > 10K файлов → graph view медленный, настроить filtering через `.obsidian/graph.json`

### Ссылки

- `.mcp.json` — main MCP config
- [MarkusPfundstein/mcp-obsidian](https://github.com/MarkusPfundstein/mcp-obsidian) — upstream project
- Альтернатива: [cyanheads/obsidian-mcp-server](https://github.com/cyanheads/obsidian-mcp-server) (TS, 445 stars) с нативной поддержкой frontmatter/tags

---

## ## ADDED REQ-2: .obsidian/ vault configuration

**Файлы:** `.obsidian/app.json`, `.obsidian/workspace.json`, `.obsidian/community-plugins.json`, `.obsidian/appearance.json`, `.obsidian/core-plugins.json`

Vault config для Obsidian desktop. `workspace.json` настраивается на монтирование `docs/` и `.claude/skills/*/cache/` как главного workspace, исключение `.git/`, `src/` (не знания), `.venv/`, `tests/`.

### Структура

```
.obsidian/
  app.json                    — основные настройки (UTF-8, markdown view, live preview)
  workspace.json              — layout (gitignored)
  appearance.json             — тема, шрифт
  core-plugins.json           — enabled core plugins (graph, backlinks, outgoing-links, tag-pane)
  community-plugins.json      — пустой список (без community plugins для minimal footprint)
  graph.json                  — graph view настройки (node size, link thickness, color groups)
  templates/
    entity.md                 — template для новых entity pages
    concept.md                — template для concept pages
    procedure.md              — template для how-to pages
```

### Обязательные настройки

- **Exclude paths** (из индекса Obsidian): `src/`, `.venv/`, `.git/`, `tests/`, `data/`, `build/`, `node_modules/`, `__pycache__/`
- **Attachments folder**: `docs/wiki/_attachments/` (для будущих images)
- **New note location**: `docs/wiki/drafts/`
- **Templates folder**: `.obsidian/templates/`
- **Default format**: markdown, UTF-8, LF line endings

### Сценарий 1: Vault открывается в Obsidian

**Given** `.obsidian/` создана с правильным workspace.json
**When** пользователь выбирает `D:/1С-Framework` в Obsidian → Open vault
**Then** Obsidian открывает без ошибок
**And** sidebar отображает `docs/`, `docs/architecture/`, `docs/roadmap/`, `docs/wiki/`
**And** `src/` и `.venv/` не видны (excluded)

### Сценарий 2: Graph view работает

**Given** vault открыт, обработано ≥30 файлов
**When** пользователь открывает graph view (Ctrl+G)
**Then** отображается ≥30 узлов
**And** узлы с wiki-links соединены рёбрами
**And** filter по tag работает

### Граничные условия

- `workspace.json` в git → конфликты между разработчиками → добавить в `.gitignore`
- Graph view медленный на large vaults → настроить `graph.json` с фильтрами
- Obsidian на macOS vs Windows vs Linux → одинаковые JSON configs, но пути разные
- Первый запуск — Obsidian индексирует vault (~30-60s) → не блокер

### Ссылки

- `.gitignore` — добавить `.obsidian/workspace.json`, `.obsidian/workspace-mobile.json`
- `docs/wiki/` — целевой каталог для новых wiki pages
- [Obsidian vault configuration docs](https://help.obsidian.md)

---

## ## ADDED REQ-3: docs/wiki/ структура

**Файлы:** `docs/wiki/_index.md`, `docs/wiki/SCHEMA.md`, `docs/wiki/log.md`

Новый каталог `docs/wiki/` с структурой:

```
docs/wiki/
  _index.md             — wiki map (links to categories)
  SCHEMA.md             — правила ведения (5-layer model, frontmatter rules, cross-references)
  log.md                — хронология L2→L3 промоций
  entities/             — structured entity pages (auto-exported из LightRAG graph, Фаза 4)
  concepts/             — concept pages (manual + auto-promoted from L2)
  procedures/           — how-to guides
  patterns/             — architectural patterns (split из docs/architecture/PATTERNS.md)
  drafts/               — auto-generated drafts (gitignored до approval)
  _attachments/         — images, diagrams, attachments
```

### Frontmatter format

Каждая wiki-страница имеет обязательный frontmatter:

```markdown
---
unified_id: wiki:obsidian-vault:patterns/zai-provider-selection.md
content_type: wiki
source: wiki_promoter | manual | graph_exporter
created_at: 2026-04-14T12:00:00Z
updated_at: 2026-04-14T15:30:00Z
status: draft | approved | deprecated
tags: [performance, llm-rotation, delegation]
related:
  - wiki:obsidian-vault:concepts/token-economy.md
  - wiki:obsidian-vault:entities/z-ai-provider.md
promoted_from:                    # optional, только если auto-promoted
  pattern_id: abc123
  confidence: 0.92
  usage_count: 8
---

# Zai Provider Selection

Контент страницы...
```

### Сценарий 1: Страница создаётся с правильным frontmatter

**Given** `WikiPromoter.try_promote_pattern()` из Фазы 3 создаёт draft
**When** файл `docs/wiki/drafts/zai-providers.md` записывается через `MemoryCube.to_wiki_page()`
**Then** frontmatter содержит все обязательные поля
**And** `unified_id` корректно сформирован `wiki:obsidian-vault:drafts/zai-providers.md`
**And** `source: wiki_promoter`
**And** `promoted_from` содержит pattern metadata

### Сценарий 2: Schema validation блокирует invalid page

**Given** developer создаёт `docs/wiki/concepts/test.md` без поля `unified_id`
**When** pre-commit hook (Фаза 3) запускается `kb-lint --ci`
**Then** validation fail с ошибкой `Missing required frontmatter field: unified_id`
**And** commit блокируется

### Граничные условия

- `docs/wiki/drafts/*.md` → в `.gitignore` до approval (drafts временные)
- Пустой файл → `WIKI_ERROR` в docs-change-tracker
- Кириллица в slug → разрешена, но рекомендуется latin transliteration
- Очень большой wiki (>1000 страниц) → настроить Obsidian graph filters

### Ссылки

- `docs/wiki/SCHEMA.md` — будет создан в Фазе 2 с детальными правилами
- `src/memory/orchestrator/memcube.py::MemoryCube.to_wiki_page()` — Phase 0 implementation

---

## ## MODIFIED REQ-4: Миграция существующих docs/architecture/

**Файлы:** `docs/architecture/overview.md`, `triad-architecture.md`, `ralph-wiggum.md`, `hooks-reference.md`, `skills-reference.md`, `PATTERNS.md`, `bsl-integration.md`, `core-framework-separation.md`
**Было:** 8 markdown файлов без frontmatter, без wiki-links, без cross-references
**Стало:** те же файлы с добавленным YAML frontmatter и `[[wiki-links]]` на связанные документы

### Изменения (non-breaking)

Для каждого из 8 файлов:
1. **Добавить frontmatter** в начало (не менять body content):
   ```yaml
   ---
   unified_id: wiki:obsidian-vault:architecture/<filename>.md
   content_type: wiki
   source: manual
   created_at: <git first commit timestamp>
   updated_at: <git last commit timestamp>
   status: approved
   tags: [architecture, ...]
   related: []  # заполняется постепенно
   ---
   ```
2. **Добавить wiki-links** там, где уже есть упоминания других документов (например, `triad-architecture.md` упоминает hooks → добавить `[[hooks-reference]]`)
3. **НЕ трогать** body content — сохранить existing text, заголовки, код-блоки

### Split `PATTERNS.md` (опционально)

`docs/architecture/PATTERNS.md` содержит каталог 15 архитектурных + 13 автоматизационных паттернов. Опциональная задача:
- Разбить на отдельные файлы `docs/wiki/patterns/<pattern-name>.md`
- Оригинальный `PATTERNS.md` остаётся как index-страница с wiki-links на детальные
- Каждый паттерн получает independent entity-level page для точечной ссылаемости

### Сценарий 1: triad-architecture.md мигрирован

**Given** `docs/architecture/triad-architecture.md` без frontmatter
**When** migration script запускается: `python scripts/migrate_docs_architecture.py`
**Then** файл получает frontmatter с `unified_id`, `status: approved`
**And** body content не меняется (git diff показывает только frontmatter addition)
**And** в body добавлены `[[hooks-reference]]` / `[[skills-reference]]` где упоминались

### Сценарий 2: Split PATTERNS.md

**Given** `docs/architecture/PATTERNS.md` с 28 паттернами
**When** split script запускается: `python scripts/split_patterns.py`
**Then** создаются 28 файлов `docs/wiki/patterns/<slug>.md`
**And** каждый с frontmatter + контент соответствующего раздела
**And** оригинальный `PATTERNS.md` перепрофилируется как index с `[[wiki-links]]`

### Граничные условия

- Файл уже имеет frontmatter (edge case) → migration skip, log notice
- Body содержит `[[invalid]]` raw text → оставляется как есть, не создаются broken links
- Git history не даёт точный created_at → fallback на file mtime
- Миграция прерывается посередине → backup файла сохранён (`.bak`), restore через script

### Ссылки

- `docs/architecture/` — каталог существующих 8 файлов
- `scripts/migrate_docs_architecture.py` — новый migration script (создаётся в Фазе 1)
- `scripts/split_patterns.py` — новый split script (опциональный)

---

## Регрессия

Фаза 1 **НЕ ДОЛЖНА** ломать:

- [ ] Существующие ссылки на `docs/architecture/*.md` из других mg файлов и skills — frontmatter addition не меняет markdown rendering на GitHub/VS Code
- [ ] `docs/roadmap/*.md` файлы — не мигрируются в этой фазе (отдельная задача)
- [ ] Memory-first-hook Layer 3 поиск по `user-level memory/` — не затрагивается
- [ ] Skill-router Qdrant `skill_library` индексирование — не затрагивается (skills в `.claude/skills/`, не в `docs/wiki/`)
- [ ] Git history — все изменения commit-friendly (diff показывает только добавленный frontmatter)

## Новые тесты

```
tests/unit/scripts/
  test_migrate_docs_architecture.py   — frontmatter injection без изменения body
  test_split_patterns.py              — PATTERNS.md split валидация

tests/integration/
  test_obsidian_vault_structure.py    — все обязательные папки существуют
  test_wiki_links_validity.py         — [[wiki-link]] targets существуют

tests/fixtures/
  sample_architecture_file.md         — до миграции
  sample_architecture_file_migrated.md — после миграции (golden)
```
