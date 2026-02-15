---
topic: "MCP Lazy Loading & Token Optimization"
domain: "tools"
category: "pattern"
created: "2026-02-12"
last_verified: "2026-02-12"
version: "mcp-cli v0.3.0"
source_urls:
  - "https://github.com/philschmid/mcp-cli"
  - "https://www.philschmid.de/mcp-cli"
  - "https://www.anthropic.com/engineering/code-execution-with-mcp"
  - "https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1576"
keywords: ["mcp", "lazy loading", "token optimization", "tool search", "mcp-cli", "allowedTools"]
---

# MCP Lazy Loading & Token Optimization

## 1. Идентификация

**Что это:** Стратегии сокращения расхода токенов на MCP tool definitions в контексте LLM-агентов.
**Для чего:** Решение проблемы token bloat при >15 MCP tools (каждый tool = 550-850 токенов описания).
**Когда использовать:** При 20+ MCP tools или объединении нескольких MCP-серверов.

**Проблема в цифрах:**
- 12 tools = ~8,400 токенов (4.2% от 200K) — **приемлемо**
- 30 tools = ~21,000 токенов (10.5%) — **порог автоматического Tool Search**
- 60 tools = ~42,000 токенов (21%) — **критично, нужен lazy loading**
- 135 tools (Docker MCP) = ~125,964 токенов (63%) — **катастрофа**

**Побочные эффекты bloat:** LLM чаще выбирает неправильный tool, растёт галлюцинация параметров, "lost in the middle" — tools из центра списка игнорируются. Рекомендация: ≤10-15 tools одновременно.

---

## 2. Решения (от простого к сложному)

### Уровень 0: allowedTools фильтрация (0 effort)
В `mcp_servers.json` или Claude Code settings указать только нужные tools per-project:
```json
{
  "mcpServers": {
    "pdf-framework": {
      "command": "...",
      "allowedTools": ["search_documents", "ask_question", "index_pdf"]
    }
  }
}
```

### Уровень 1: Claude Code Tool Search (автоматический)
Встроен в Claude Code (январь 2026). Активируется автоматически при >10% контекста.
- **Сокращение**: 85% (77K → 8.7K)
- **Точность выбора**: 49% → 74% (Opus 4)
- **Effort**: 0 (zero-config)
- **Ограничение**: только Claude Code

### Уровень 2: mcp-cli (Philipp Schmid, Google DeepMind)
CLI-утилита для lazy discovery MCP tools. MIT, TypeScript/Bun, кросс-платформенный бинарник.
- **Сокращение**: ~99% (47K → 400 токенов)
- **3 команды**: `mcp-cli info` → `mcp-cli info <server> <tool>` → `mcp-cli call <server> <tool> '{...}'`
- **Демон**: пул соединений, 60s timeout, worker pool (5 параллельных)
- **Effort**: 1 день интеграции
- **Для**: кросс-агентная совместимость (не только Claude Code)

### Уровень 3: Enterprise (ContextForge, Speakeasy, Docker MCP Catalog)
Gateway-решения с маршрутизацией, governance, OAuth. Для 100+ tools.

---

## 3. Наш контекст (PDF Framework + 1C-Enterprise)

### Текущее состояние
- PDF Framework: 9 skills + 12 MCP tools + 12 hooks
- 1C-Enterprise: ~37 skills + 5+ MCP серверов + 50+ hooks

### Прогноз при объединении
- Skills: 46 × ~400 = 18,400 токенов (9.2%) — skills уже lazy (Claude Code загружает только при вызове)
- MCP Tools: ~30 × ~700 = 21,000 токенов (10.5%) — **пересечён порог Tool Search**

### Рекомендованная стратегия
1. **Сейчас**: `allowedTools` per-project в settings.json
2. **При 30+ tools**: Claude Code Tool Search (автоматический)
3. **При 60+ или мульти-агент**: mcp-cli

---

## 4. Альтернативные подходы

| Решение | Сокращение | Платформа | Тип |
|---------|-----------|-----------|-----|
| mcp-cli | ~99% | Любой агент с bash | CLI |
| Claude Code Tool Search | ~85% | Claude Code only | Встроенная |
| Anthropic Code Execution | ~98.7% | Sandbox | Паттерн |
| Speakeasy Dynamic Toolsets | ~96% | Speakeasy SDK | SDK |
| lazy-mcp (voicetreelab) | Значительное | Любой | MCP-прокси |
| Amp Skills | Зависит | Amp | Платформа |

---

## 5. Источники

- **mcp-cli**: https://github.com/philschmid/mcp-cli (867 stars, MIT, v0.3.0)
- **Anthropic Code Execution**: https://www.anthropic.com/engineering/code-execution-with-mcp
- **SEP-1576 (Huawei)**: https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1576
- **Lazy-load issue**: https://github.com/anthropics/claude-code/issues/11364
- **Наш документ**: docs/MCP_CLI_Исследование.md
