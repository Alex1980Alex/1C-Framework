# Фаза 49: Unified Memory System

**Tier:** 3 — Memory и AI-сервисы
**Статус:** DONE
**Зависимости:** Фаза 44 (Infrastructure), Qdrant running
**Оценка:** ~8 часов
**Блокирует:** Фаза 51 (Task Master)

---

## Цель

Перенести 4 системы памяти и объединить их через Memory Orchestrator с UnifiedID и federated search.

---

## 4 Memory системы

### 1. Memory Orchestrator (ROUTER)

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\memory-orchestrator\` |
| **Цель** | `D:\1С-Framework\src\memory\orchestrator\` |
| **Версия** | v2.2.0 |
| **Tools** | 46+ |

**Возможности:**
- UnifiedID: `episodic:memory-type:identifier`
- Link Registry: cross-system references
- Federated search: поиск по всем 4 системам
- Graph traversal: relationship strength

### 2. AI Memory System (EPISODIC)

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\ai-memory-system\` |
| **Цель** | `D:\1С-Framework\src\memory\ai_memory\` |
| **Backend** | TimescaleDB + Qdrant + Neo4j |
| **Qdrant коллекция** | `ai_memory` (768d) |

**Возможности:**
- Conversations (TimescaleDB hypertable)
- Messages с importance scoring
- Semantic search по embeddings
- Entity extraction и relations (Neo4j)

### 3. Vector Memory MCP (SEMANTIC)

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\vector-memory-mcp\` |
| **Цель** | `D:\1С-Framework\src\memory\vector_memory\` |
| **Qdrant коллекция** | `learned_patterns` (768d, Google Gemini) |

**Возможности:**
- Confidence-weighted pattern learning
- Mutable confidence scores
- Decay mechanism для устаревших паттернов
- Evidence linking

### 4. Skill Learning MCP (LEARNING)

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\skill-learning-mcp\` |
| **Цель** | `D:\1С-Framework\src\memory\skill_learning\` |

**Возможности:**
- Захват паттернов из PostToolUse hook
- Персистенция навыков
- Связь с vector-memory для хранения

---

## Шаги

### 49.1 Перенести Memory Orchestrator

```bash
cp -r D:/1C-Enterprise_Framework/memory-orchestrator/src src/memory/orchestrator/
```

### 49.2 Перенести AI Memory System

```bash
cp -r D:/1C-Enterprise_Framework/ai-memory-system/mcp_local_scripts src/memory/ai_memory/
cp -r D:/1C-Enterprise_Framework/ai-memory-system/services src/memory/ai_memory/
```

**Решение по TimescaleDB:** использовать SQLite fallback если TimescaleDB недоступен (docker profile `memory`).

### 49.3 Перенести Vector Memory MCP

```bash
cp D:/1C-Enterprise_Framework/vector-memory-mcp/server.py src/memory/vector_memory/
```

### 49.4 Перенести Skill Learning MCP

```bash
cp D:/1C-Enterprise_Framework/skill-learning-mcp/server.py src/memory/skill_learning/
```

### 49.5 Адаптировать Qdrant клиенты

Все memory системы используют общий Qdrant (localhost:6333) с разными коллекциями:
- `ai_memory` — 768d embeddings
- `learned_patterns` — 768d, Google Gemini text-embedding-004

### 49.6 UnifiedID система

Формат: `episodic:memory-type:identifier`

| Тип | Memory система | Пример |
|-----|---------------|--------|
| `episodic:memory-ai` | memory-ai | Важные сообщения |
| `episodic:conversation` | conversation-memory | История сессий |
| `semantic:vector` | vector-memory | Learned patterns |
| `documentation:1c-docs` | 1c-docs-rag | Reference docs |

### 49.7 Интеграционный тест

`tests/integration/test_memory_unified.py`:
- Federated search по всем 4 системам
- UnifiedID разрешение
- Cross-system link traversal

### 49.8 Зарегистрировать MCP серверы

```json
"memory-ai": { ... },
"conversation-memory": { ... },
"vector-memory": { ... }
```

---

## Qdrant коллекции

| Коллекция | Dims | Embedding | Memory система |
|-----------|------|-----------|---------------|
| `ai_memory` | 768 | nomic-embed-text (Ollama) | AI Memory |
| `learned_patterns` | 768 | Google text-embedding-004 | Vector Memory |

---

## Чеклист завершения

- [x] `src/memory/orchestrator/` — Memory Orchestrator
- [x] `src/memory/ai_memory/` — AI Memory System
- [x] `src/memory/vector_memory/` — Vector Memory MCP
- [x] `src/memory/skill_learning/` — Skill Learning MCP
- [x] Qdrant коллекции ai_memory, learned_patterns доступны
- [x] UnifiedID система работает
- [x] Federated search возвращает результаты
- [x] 3 MCP сервера зарегистрированы в .mcp.json
- [x] Skill `memory-unified/SKILL.md` создан
- [x] Hook `memory-sync.py` (Stop) создан
- [ ] Git commit: `feat: Phase 49 — Unified Memory System`
