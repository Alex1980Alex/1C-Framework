# Фаза 54: Infrastructure Tools (Lazy MCP + Docker + AST Grep)

**Tier:** 4 — Расширения
**Статус:** DONE
**Зависимости:** Фазы 44-48 (все Tier 1-2)
**Оценка:** ~5 часов

---

## Цель

Перенести инфраструктурные компоненты: lazy-mcp proxy, Docker MCP orchestration, AST grep, BSL semantic diff.

---

## Компоненты

### Lazy MCP Proxy

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\lazy-mcp\` |
| **Цель** | `D:\1С-Framework\infra\lazy-mcp\` |
| **Runtime** | Python (venv) |
| **3 meta-tools** | `recommend_tools`, `get_tools_in_category`, `execute_tool` |
| **Config** | `config/registry.yaml` (9 категорий, 20+ серверов) |

### Docker MCP Pilot

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\docker-mcp-pilot\` |
| **Цель** | `D:\1С-Framework\infra\docker-mcp\` |
| **Статус** | POC Phase 1 |

### AST Grep MCP

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\ast-grep-mcp\` |
| **Цель** | `D:\1С-Framework\tools\ast-grep-mcp\` |
| **Runtime** | Python (venv) |
| **Timeout** | 60s |

### BSL Semantic Diff

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\scripts\bsl-semantic-diff\` |
| **Цель** | `D:\1С-Framework\tools\bsl-semantic-diff\` |
| **Runtime** | Python |

---

## Шаги

### 54.1 Перенести Lazy MCP

```bash
cp -r D:/1C-Enterprise_Framework/lazy-mcp infra/lazy-mcp
rm -rf infra/lazy-mcp/.venv
```

Пересоздать venv:
```bash
cd infra/lazy-mcp && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

**Адаптация registry.yaml:**
- Обновить все пути с `D:/1C-Enterprise_Framework/` на `D:/1С-Framework/`
- Обновить категории: добавить PDF-серверы

### 54.2 Создать .mcp/lazy-mcp.json

Адаптировать конфигурацию из источника, обновить все пути:

```json
"lazy-mcp": {
  "command": "D:\\1С-Framework\\infra\\lazy-mcp\\.venv\\Scripts\\python.exe",
  "args": ["src/server.py"],
  "cwd": "D:\\1С-Framework\\infra\\lazy-mcp",
  "env": {
    "PYTHONIOENCODING": "utf-8",
    "LAZY_MCP_CONFIG": "D:/1С-Framework/infra/lazy-mcp/config/registry.yaml"
  },
  "timeout": 30000
}
```

### 54.3 Перенести Docker MCP

```bash
cp -r D:/1C-Enterprise_Framework/docker-mcp-pilot infra/docker-mcp
```

Содержит Docker Compose конфигурацию для MCP-серверов (POC).
Адаптировать пути и volume mounts.

### 54.4 Перенести AST Grep MCP

```bash
cp -r D:/1C-Enterprise_Framework/ast-grep-mcp tools/ast-grep-mcp
rm -rf tools/ast-grep-mcp/.venv
cd tools/ast-grep-mcp && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
```

### 54.5 Перенести BSL Semantic Diff

```bash
cp -r D:/1C-Enterprise_Framework/scripts/bsl-semantic-diff tools/bsl-semantic-diff
```

### 54.6 Обновить Docker конфигурацию

Добавить BSL-специфичные сервисы (TimescaleDB для AI Memory и др.).
Убедиться что Qdrant имеет достаточно памяти для доп. коллекций.

---

## Чеклист завершения

- [x] `infra/lazy-mcp/` — proxy работает (venv, 11 категорий, 27 серверов)
- [x] `infra/lazy-mcp/config/registry.yaml` — пути обновлены
- [x] `.mcp/lazy-mcp.json` — корректные пути
- [x] `infra/docker-mcp/` — Docker MCP Pilot (volumes обновлены)
- [x] `tools/ast-grep-mcp/` — AST Grep работает (venv, import OK)
- [x] `tools/bsl-semantic-diff/` — BSL Semantic Diff скопирован
- [x] Docker конфигурация обновлена
- [x] Lazy MCP proxy запускается и проксирует запросы
- [x] Git commit: `feat: Phase 54 — Infrastructure Tools migration`
