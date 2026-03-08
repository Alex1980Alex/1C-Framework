# Docker MCP Pilot - Результаты тестирования

> **Дата:** 2026-01-04
> **Фаза:** 1 - Pilot (Proof of Concept)
> **Статус:** ⚠️ Обнаружено фундаментальное ограничение
> **Решение:** Пересмотр подхода к Docker MCP

---

## Executive Summary

**Результат:** Pilot выявил, что **MCP серверы не могут работать в Docker как автономные сервисы** из-за архитектуры протокола MCP (stdio-based).

### Что было сделано

| Этап | Статус | Результат |
|------|--------|-----------|
| **Создание структуры** | ✅ Complete | 11 файлов создано |
| **Dockerfiles** | ✅ Complete | 5 Dockerfiles создано |
| **Сборка образов** | ✅ Complete | 5 образов собрано (1.2GB) |
| **Запуск контейнеров** | ✅ Complete | 5 контейнеров запущено |
| **Работа MCP** | ❌ Failed | **Stdio limitation** |

---

## Обнаруженная проблема

### Симптомы

```
NAMES                     STATUS
mcp-sqlite                Up 5 seconds        ✅
mcp-memory                Up 4 seconds        ✅
mcp-filesystem            Restarting (loop)   ❌
mcp-sequential-thinking   Restarting (loop)   ❌
mcp-ripgrep               Restarting (loop)   ❌
```

**Логи:**
```
Secure MCP Filesystem Server running on stdio
(затем перезапуск, т.к. нет stdin)
```

### Корневая причина

**MCP (Model Context Protocol)** использует **stdio** (стандартный ввод/вывод) для коммуникации:

```
Claude Code Client ←→ stdin/stdout ←→ MCP Server
```

**В Docker:**
```
Docker Container (no stdin connection)
  ├─ MCP Server запускается
  ├─ Ждёт ввод на stdin
  ├─ Timeout/Health check fails
  └─ Перезапуск (loop)
```

### Почему 2 сервера работают?

- **mcp-sqlite** и **mcp-memory** работают, потому что они не требуют активного stdin соединения сразу
- Они могут "ждать" в фоновом режиме

---

## Выводы

### ❌ Текущий подход НЕ работает

**Нельзя запустить MCP серверы как автономные Docker контейнеры** потому что:

1. MCP требует **bidirectional stdio** connection
2. Docker контейнеры изолированы от stdin клиента
3. Health check перезапускает "idle" серверы

### ✅ Что ДОЛЖНО работать вместо этого

**Подход 1: Docker для зависимостей + Native MCP**

```
┌─────────────────────────────────────────────────────────────┐
│  HYBRID ARCHITECTURE (Recommended)                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Dependencies (Docker):                                     │
│  ├─ Neo4j (graph database)                                  │
│  ├─ Qdrant (vector search)                                  │
│  ├─ TimescaleDB (time-series)                               │
│  ├─ Redis (cache)                                           │
│  └─ PostgreSQL (relational)                                 │
│                                                              │
│  MCP Servers (Native):                                      │
│  ├─ ast-grep-mcp (Python venv)                              │
│  ├─ unified-memory (Python)                                 │
│  ├─ 1c-docs-rag (Python)                                    │
│  ├─ serena (UV)                                             │
│  └─ ... (all 33 servers)                                    │
│                                                              │
│  Benefits:                                                  │
│  ✅ Dependencies в Docker (изоляция, easy setup)            │
│  ✅ MCP servers native (stdio works correctly)              │
│  ✅ Best of both worlds                                     │
└─────────────────────────────────────────────────────────────┘
```

**Подход 2: MCP Gateway с stdio proxy**

```
┌─────────────────────────────────────────────────────────────┐
│  DOCKER MCP GATEWAY (Advanced)                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Gateway Container:                                         │
│  ├─ Accepts MCP connections from clients                    │
│  ├─ Routes to appropriate MCP server                       │
│  └─ Manages stdio pipes                                     │
│                                                              │
│  MCP Servers:                                               │
│  ├─ Run in containers or native                             │
│  └─ Connect to Gateway via pipes/unix sockets              │
│                                                              │
│  Requires:                                                  │
│  ❌ Custom Gateway implementation                           │
│  ❌ Pipe management                                         │
│  ❌ Complex orchestration                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Рекомендуемое решение

### Гибридная архитектура (Практичная)

**Шаг 1: Dependencies в Docker**

Создать `docker-compose.dependencies.yml`:

```yaml
version: '3.8'

services:
  neo4j:
    image: neo4j:5.15
    container_name: 1c-neo4j
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    container_name: 1c-qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  timescaledb:
    image: timescale/timescaledb:latest-pg14
    container_name: 1c-timescaledb
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=ai_memory
      - POSTGRES_USER=ai_user
      - POSTGRES_PASSWORD=password
    volumes:
      - timescaledb_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    container_name: 1c-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  neo4j_data:
  qdrant_data:
  timescaledb_data:
  redis_data:
```

**Шаг 2: MCP серверы нативно**

Оставить `.mcp.json` как есть для MCP серверов.

**Шаг 3: Единая команда запуска**

```bash
# Start dependencies
docker-compose -f docker-compose.dependencies.yml up -d

# MCP servers work natively (as before)
# Claude Code connects to both Docker + native
```

### Преимущества гибридного подхода

| Аспект | Docker MCP | Hybrid |
|--------|------------|--------|
| **Dependencies** | ✅ Изолированы | ✅ Изолированы |
| **MCP servers** | ❌ Stdio проблемы | ✅ Работают |
| **Setup complexity** | Высокая | Средняя |
| **Maintainability** | Средняя | Высокая |
| **Flexibility** | Низкая | Высокая |

---

## Что делать дальше

### Вариант A: Гибридный подход (Рекомендуется)

1. **Создать `docker-compose.dependencies.yml`**
2. **Переместить зависимости в Docker:**
   - Neo4j
   - Qdrant
   - TimescaleDB
   - Redis
   - PostgreSQL

3. **Оставить MCP серверы нативными**

4. **Создать единый start script:**
   ```bash
   # start-all.bat
   docker-compose -f docker-compose.dependencies.yml up -d
   echo "Dependencies started. MCP servers work via .mcp.json"
   ```

### Вариант B: Официальный Docker MCP Gateway

Использовать официальное решение от Docker (если доступно):

- [Docker MCP Toolkit](https://docs.docker.com/ai/mcp-catalog-and-toolkit/toolkit/)
- [Dynamic MCP](https://docs.docker.com/ai/mcp-catalog-and-toolkit/dynamic-mcp/)

**Но это требует:**
- Docker Desktop 4.42+
- Специальной конфигурации
- Возможно, платной подписки

---

## Файлы созданы (для справки)

| Файл | Статус | Примечание |
|------|--------|------------|
| docker-compose.yml | ✅ | Не работает (stdio limitation) |
| dockerfiles/*.dockerfile | ✅ | Собраны успешно |
| registry/tool-registry.json | ✅ | Полезен для future |
| scripts/*.bat | ✅ | Могут быть адаптированы |
| README.md | ✅ | Требует обновления |
| IMPLEMENTATION-REPORT.md | ✅ | Актуален |

---

## Статистика тестирования

| Метрика | Значение |
|---------|----------|
| **Время на сборку** | ~10 минут (5 образов) |
| **Размер образов** | ~1.2 GB |
| **Контейнеров запущено** | 5/5 |
| **Работающих корректно** | 0/5 |
| **Проблема** | MCP stdio limitation |

---

## Заключение

### ❌ Pilot провалился (как автономные MCP контейнеры)

Но это **ожидаемый результат** - MCP протокол не предназначен для работы в изолированных Docker контейнерах.

### ✅ Pilot дал ценную информацию

1. **Поняли ограничения MCP** (stdio-based)
2. **Собрали работающие Dockerfiles** (могут быть использованы)
3. **Создали Tool Registry** (будет полезен для Dynamic MCP)
4. **Определили правильный подход** (Hybrid architecture)

### 🎯 Рекомендация

**Использовать гибридный подход:**
- Dependencies → Docker
- MCP servers → Native

Это даст:
- ✅ Лёгкий setup dependencies
- ✅ Работающие MCP серверы
- ✅ Практическое решение

---

**Дата:** 2026-01-04
**Автор:** Claude Code
**Вердикт:** ❌ Autonomous MCP containers не работают
**Решение:** Hybrid architecture (Docker for dependencies + Native MCP)
