# Фаза 51: Task Master + Development Pipeline

**Tier:** 3 — Memory и AI-сервисы
**Статус:** TODO
**Зависимости:** Фазы 44, 49 (Memory)
**Оценка:** ~5 часов

---

## Цель

Перенести AI-управление задачами и CI/CD пайплайн, интегрировать с существующим Task Protocol.

---

## Компоненты

### Claude Task Master

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\claude-task-master\` |
| **Цель** | `D:\1С-Framework\infra\task-master\` |
| **Runtime** | Node.js (npx task-master-ai) |
| **LLM** | Z.AI GLM-5 (via Anthropic API) |
| **Tools** | 38 |

### Development Pipeline

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\development-pipeline\` |
| **Цель** | `D:\1С-Framework\infra\pipeline\` |
| **Технологии** | Python |
| **LOC** | ~3,000 |

---

## Шаги

### 51.1 Оценить совместимость Task Master с Task Protocol

**Существующий Task Protocol в 1С-Framework:**
- `idle -> classified -> [decomposed] -> skill_checked -> ALLOW Write/Edit`
- Enforcer hooks: `task-protocol-enforcer.py`, `task-protocol-observer.py`
- TaskCreate/TaskUpdate/TaskList tools (built-in Claude Code)

**Claude Task Master:**
- 38 tools для AI-декомпозиции задач
- 7 LLM провайдеров
- npx пакет (standalone)

**Решение:** Task Master как дополнительный инструмент, НЕ замена Task Protocol. Используется для сложной AI-декомпозиции.

### 51.2 Перенести Task Master

```bash
cp -r D:/1C-Enterprise_Framework/claude-task-master infra/task-master
rm -rf infra/task-master/node_modules
```

### 51.3 Перенести Development Pipeline

```bash
cp -r D:/1C-Enterprise_Framework/development-pipeline infra/pipeline
```

Ключевые файлы:
- `artifact_store.py` — хранение артефактов
- `constants.py` — конфигурация
- `models.py` — модели данных
- `agents/` — pipeline агенты
- `cli/` — CLI

### 51.4 Интегрировать с hooks

Pipeline триггерится от существующих hooks:
- `auto-git-save.py` (Stop) -> pipeline artifact save
- `code-verify-reminder.py` (PostToolUse) -> pipeline quality check

### 51.5 Зарегистрировать в .mcp.json

```json
"task-master-ai": {
  "command": "npx",
  "args": ["-y", "--package=task-master-ai", "task-master-ai"],
  "cwd": "D:\\1С-Framework\\infra\\task-master",
  "env": {
    "ANTHROPIC_API_KEY": "${DEEP_REASONING_API_KEY}",
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "TASKMASTER_PROJECT_ROOT": "D:/1С-Framework/infra/task-master"
  },
  "timeout": 180000
}
```

---

## Чеклист завершения

- [ ] Анализ совместимости Task Master + Task Protocol выполнен
- [ ] `infra/task-master/` содержит Task Master
- [ ] `infra/pipeline/` содержит Development Pipeline
- [ ] `.mcp.json` содержит `task-master-ai`
- [ ] Pipeline интегрирован с hooks
- [ ] Git commit: `feat: Phase 51 — Task Master + Dev Pipeline`
