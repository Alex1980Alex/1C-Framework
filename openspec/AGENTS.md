# OpenSpec — AGENTS.md

> Инструкции для AI-агентов по работе с OpenSpec-workflow в этом репозитории.
> Источники-эталоны: реальные change'ы под `openspec/changes/` (`gkstcplk-mcp-toolkit-extension`, `gkstcplk-2256-…`).

## Workflow lifecycle

```
ANALYSIS (skill analyze-1c-task-v2)
    │ ANALYSIS-REPORT.md
    ▼
PROPOSE (/opsx:propose <change-name>)
    │ openspec/changes/<change>/ {proposal, design, tasks, specs/<cap>/spec.md}
    ▼
APPROVE (/opsx:approve <change>)
    │ обсуждение Open Questions; добавление reviews; критика
    ▼
APPLY (/opsx:apply <change>)
    │ фактическая реализация через skill implement-1c-task v2.7 (8 этапов)
    ▼
ARCHIVE (/opsx:archive <change>)
    │ перенос в openspec/changes/archive/
```

## Структура change-каталога

```
openspec/changes/<change-id>/
├── proposal.md                  # what & why
├── design.md                    # how (опц., но рекомендован для feature)
├── tasks.md                     # шаги реализации (нумерованные)
└── specs/                       # delta-specs по capability
    └── <capability>/
        └── spec.md              # ADDED/MODIFIED/REMOVED + Requirements
```

## Соглашения по именованию

- **change-id**: `kebab-case` ASCII (e.g. `gkstcplk-2507-auto-disallow-by-nomenclature`). Кириллица в id ломает git/FS на Windows.
- **Task ID для бизнес-задачи** (например `GKSTCPLK-2507`) фиксируется в `proposal.md` шапке и используется как тег комментариев BSL-кода: `// GKSTCPLK-2507` либо парные маркеры `// GKSTCPLK-2507 Начало` / `// GKSTCPLK-2507 Конец`.
- **capability** (имя папки под `specs/`): семантическое kebab-case (e.g. `disallow-by-nomenclature-overlay`, `mcp-metadata-provider`).

## Шаблоны артефактов (минимум)

**proposal.md** обязательные секции:
- `## Summary`
- `## Motivation`
- `## Proposed Solution`
- `## Alternatives Considered`
- `## Impact` (с чекбоксами Breaking changes / DB migrations / API changes)
- `## Open Questions` (для approve gate)

**tasks.md** — нумерованные секции (1, 2, 3…) с задачами в формате `- [ ] **N.M** описание`.

**specs/<cap>/spec.md** обязательные секции:
- `## ADDED` / `## MODIFIED` / `## REMOVED` (любая комбинация)
- `## Requirements` с `### REQ-N: title` + bullet points.

## MCP-tools (openspec-mcp server)

| Tool | Назначение |
|---|---|
| `openspec_create_change` | scaffold нового change'а (proposal.md + tasks.md) |
| `openspec_save_proposal` | первичная запись proposal/tasks (НЕ перезапишет existing) |
| `openspec_show_change` | summary + структура change'а |
| `openspec_list_changes` | все active+archived change'ы |
| `openspec_validate_change` | валидация (требует AGENTS.md + project.md) |
| `openspec_critique_proposal` | feedback по содержанию |
| `openspec_request_approval` / `openspec_approve_change` / `openspec_archive_change` | управление жизненным циклом |
| `openspec_get_tasks` / `openspec_update_task` / `openspec_batch_update_tasks` | управление прогрессом задач |

## Связь с другими skills

- **analyze-1c-task-v2** → готовит ANALYSIS-REPORT → служит входом для `/opsx:propose`.
- **implement-1c-task v2.7** → запускается из `/opsx:apply` для реализации tasks.md.
- **brownfield-validate** → запускается после apply (Gap + Design + Impl проверки).

## Запрещено

- Перезаписывать архивированные change'ы (`openspec/changes/archive/`).
- Менять `change-id` после создания (id используется как ключ в гитлогах и UI).
- Создавать `proposal.md` без обязательных секций (см. шаблон выше) — `validate` упадёт.
- Использовать кириллицу в `change-id` или именах capability — ломает Windows/Git path handling.
