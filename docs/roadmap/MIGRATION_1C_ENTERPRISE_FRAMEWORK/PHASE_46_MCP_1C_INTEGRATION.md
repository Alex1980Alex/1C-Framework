# Фаза 46: MCP 1C Integration + Server

**Tier:** 2 — Основные сервисы
**Статус:** DONE
**Зависимости:** Фаза 44 (Infrastructure)
**Оценка:** ~4 часа

---

## Цель

Перенести фреймворк разработки MCP-серверов для 1С и готовый MCP-сервер для взаимодействия с платформой.

---

## Компоненты

### MCP 1C Integration

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\mcp-1c-integration\` |
| **Цель** | `D:\1С-Framework\src\bsl\mcp_integration\` |
| **Технологии** | Python + 1C Extension |
| **LOC** | ~3,000 |

**Компоненты:**
- `src/1c_ext/` — расширение 1С, реализующее MCP-протокол
- `src/py_server/` — опциональный Python proxy сервер
- Tool implementation framework
- Resource management
- Prompt templates
- OAuth2 authentication

### MCP 1C Server

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\mcp-1c-server\` |
| **Цель** | `D:\1С-Framework\src\bsl\mcp_server\` |
| **Технологии** | Python |
| **LOC** | ~2,000 |

### BSL Platform Context (Java JAR)

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\mcp-servers\mcp-bsl-context-0.3.1.jar` |
| **Цель** | `D:\1С-Framework\tools\mcp-jars\mcp-bsl-context-0.3.1.jar` |
| **Runtime** | Java (Zulu-17) |
| **Timeout** | 30s |

Предоставляет API платформы 1С:8.3.27 — типы, методы, свойства.

---

## Шаги

### 46.1 Перенести mcp-1c-integration

```bash
cp -r D:/1C-Enterprise_Framework/mcp-1c-integration/src src/bsl/mcp_integration/
cp D:/1C-Enterprise_Framework/mcp-1c-integration/README.md src/bsl/mcp_integration/
```

**Целевая структура:**
```
src/bsl/mcp_integration/
├── __init__.py
├── 1c_ext/              # 1C Extension source
│   ├── Configuration.xml
│   └── ... (1C XML файлы)
├── py_server/           # Python proxy
│   ├── __init__.py
│   ├── server.py
│   └── tools/
├── README.md
```

### 46.2 Перенести mcp-1c-server

```bash
cp -r D:/1C-Enterprise_Framework/mcp-1c-server src/bsl/mcp_server/
```

**Целевая структура:**
```
src/bsl/mcp_server/
├── __init__.py
├── server.py            # MCP server entry point
├── tools/               # Tool implementations
├── config.py            # Configuration
└── README.md
```

### 46.3 Скопировать Java JAR

```bash
cp D:/1C-Enterprise_Framework/mcp-servers/mcp-bsl-context-0.3.1.jar tools/mcp-jars/
```

**Проверка:**
```bash
java -jar tools/mcp-jars/mcp-bsl-context-0.3.1.jar --help
```

**Требования:**
- Java: Zulu-17 (`JAVA_HOME=C:\Program Files\Zulu\zulu-17`)
- Platform: `C:\Program Files\1cv8\8.3.27.1859`

### 46.4 Адаптировать пути и конфиг

- Обновить импорты: `mcp_1c_server.*` -> `src.bsl.mcp_server.*`
- Обновить конфиг: пути к 1С платформе из `.env`
- Создать `__init__.py` во всех пакетах

### 46.5 Зарегистрировать в .mcp.json

```json
"bsl-platform-context": {
  "command": "java",
  "args": ["-Dfile.encoding=UTF-8", "-jar",
           "D:\\1С-Framework\\tools\\mcp-jars\\mcp-bsl-context-0.3.1.jar",
           "--platform-path", "C:\\Program Files\\1cv8\\8.3.27.1859",
           "--verbose"],
  "env": { "JAVA_HOME": "C:\\Program Files\\Zulu\\zulu-17" },
  "timeout": 30000
}
```

### 46.6 Тест и документация

- Ручной тест: вызов MCP tool из Claude Code -> получить метаданные типа
- Создать `docs/api/bsl-mcp.md` с описанием всех tools

---

## Чеклист завершения

- [x] `src/bsl/mcp_integration/` содержит фреймворк (1c_ext + build/MCP_Сервер.cfe + README.md)
- [x] `src/bsl/mcp_server/` содержит сервер (10 .py файлов: config, main, mcp_server, onec_client, stdio_server, http_server, auth/oauth2)
- [x] `tools/mcp-jars/mcp-bsl-context-0.3.1.jar` скопирован (41 MB)
- [x] Java Zulu-17 проверена: `java -version` → 17.0.13
- [x] `.mcp.json` содержит `bsl-platform-context`
- [x] Импорты работают: `from src.bsl.mcp_server import Config, MCPProxy, OneCClient`
- [ ] MCP tool возвращает метаданные 1С (требует запущенную 1С)
- [ ] `docs/api/bsl-mcp.md` создан
- [ ] Git commit: `feat: Phase 46 — MCP 1C Integration + Server`
