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
