---
name: obsidian-vault
description: "Навигация и создание вики-страниц в Obsidian vault поверх проекта (wiki-links, graph view, шаблоны). Триггеры: 'obsidian', 'vault', 'wiki-страница', 'wiki-link', 'создать страницу в вики', 'граф связей'. НЕ для роадмапов/ADR — используй соответствующие структуры docs/roadmap и architecture-research."
---

# Obsidian Vault — навигация и создание вики-страниц

Obsidian vault поверх проекта: wiki-links, graph view, шаблоны. Корень vault = корень проекта (`D:\1С-Framework`).

## Быстрый справочник

| Действие | Инструмент | Путь/команда |
|----------|------------|--------------|
| Открыть vault | Obsidian app | File → Open vault → `D:\1С-Framework` |
| Создать вики-страницу | Write tool | `docs/wiki/<topic>.md` с frontmatter |
| Ссылка на страницу | Wiki-link | `[[filename]]` (без расширения) |
| Ссылка на заголовок | Wiki-link heading | `[[filename#Heading]]` |
| Найти страницы | Grep wiki-links | `grep -r '\[\[' docs/` |
| MCP доступ | `mcp__obsidian-mcp__*` | Требует Local REST API plugin |
| Шаблон новой страницы | Obsidian Templates | `.obsidian/templates/` |

## Vault Structure

```
D:\1С-Framework/           ← vault root
├── .obsidian/             ← vault config
│   ├── app.json           ← editor settings
│   ├── community-plugins.json
│   ├── core-plugins.json  ← enabled: graph, backlinks, tags, canvas, bookmarks
│   ├── appearance.json
│   ├── graph.json         ← color groups: architecture=#6A5ACD, wiki=#32A064, skills=#C87832
│   ├── templates.json     ← template folder: .obsidian/templates/
│   └── templates/         ← entity.md, concept.md, how-to.md
├── docs/
│   ├── architecture/      ← 8 docs с frontmatter + wiki-links
│   │   ├── overview.md
│   │   ├── triad-architecture.md
│   │   ├── ralph-wiggum.md
│   │   ├── hooks-reference.md
│   │   ├── skills-reference.md
│   │   ├── PATTERNS.md
│   │   ├── bsl-integration.md
│   │   └── core-framework-separation.md
│   └── wiki/
│       ├── _index.md      ← wiki map
│       ├── drafts/         ← WIP pages (auto-indexed by memory-first-hook Layer 4)
│       ├── patterns/       ← extracted patterns
│       └── assets/         ← images, attachments
├── .claude/skills/*/cache/ ← skill caches (visible in vault)
└── MEMORY.md              ← auto-memory index
```

## Wiki-link Conventions

| Тип | Синтаксис | Пример |
|-----|-----------|--------|
| Простая ссылка | `[[filename]]` | `[[overview]]` |
| Ссылка на заголовок | `[[filename#Heading]]` | `[[overview#Search Strategies]]` |
| Ссылка с алиасом | `[[filename|Display Text]]` | `[[PATTERNS|Design Patterns]]` |
| Embed | `![[filename]]` | `![[overview]]` |

## Frontmatter Schema

Каждая вики-страница ДОЛЖНА иметь YAML frontmatter:

```yaml
---
status: draft | active | archived
tags: [category, subcategory]
related: [[page1]], [[page2]]
created: YYYY-MM-DD
---
```

## Templates

3 шаблона в `.obsidian/templates/`:

| Шаблон | Когда использовать | Sections |
|--------|-------------------|----------|
| `entity.md` | Описание сущности (компонент, модуль, класс) | Overview, Properties, Relationships, References |
| `concept.md` | Концепция, паттерн, подход | Problem, Solution, Examples, Trade-offs |
| `how-to.md` | Инструкция | Prerequisites, Steps, Common Issues |

## MCP Server (obsidian-mcp)

**Status**: DISABLED (требует Obsidian Desktop + Local REST API plugin)

### Setup
1. Установить [Obsidian](https://obsidian.md)
2. Открыть vault: `D:\1С-Framework`
3. Установить community plugin "Local REST API"
4. Скопировать API key → env `OBSIDIAN_API_KEY`
5. Убрать `"disabled": true` из `.mcp.json`

### Tools (7)
- `list_files_in_vault`, `list_files_in_dir`
- `get_file_contents`
- `search`
- `patch_content`, `append_content`
- `delete_file`

## Memory Integration

Wiki drafts (`docs/wiki/drafts/`) автоматически индексируются **memory-first-hook Layer 4** (weight 0.20). При UserPromptSubmit hook ищет по wiki-drafts и добавляет в federated context.

## Anti-patterns

| Плохо | Почему | Правильно |
|-------|--------|-----------|
| Wiki-links в коде (.py/.bsl) | Obsidian не парсит код | Wiki-links только в .md |
| Создавать .obsidian/ вручную при каждом проекте | Машинно-зависимый | Один раз + .gitignore для workspace.json |
| Забыть frontmatter | Нет метаданных в graph view | ВСЕГДА добавляй frontmatter |
| Ссылки типа `[text](path.md)` | Obsidian понимает, но graph view не показывает | Используй `[[filename]]` для внутренних ссылок |
