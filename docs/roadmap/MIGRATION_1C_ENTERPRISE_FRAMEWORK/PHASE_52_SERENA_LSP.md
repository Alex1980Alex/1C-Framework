# Фаза 52: Serena LSP Integration

**Tier:** 4 — Расширения
**Статус:** TODO
**Зависимости:** Фаза 44 (Infrastructure)
**Оценка:** ~4 часа

---

## Цель

Перенести Serena — LSP-агент для symbol-level code intelligence (30+ языков, включая BSL).

---

## Компонент

| Параметр | Значение |
|----------|----------|
| **Источник** | `D:\1C-Enterprise_Framework\serena\` |
| **Цель** | `D:\1С-Framework\tools\serena\` |
| **Runtime** | Python (собственный venv, serena.exe) |
| **Timeout** | 180s |
| **Языки** | 30+ (Python, TS/JS, BSL, Go, Rust, C/C++, Java, etc.) |

---

## Возможности

- Symbol-level code extraction via LSP
- Semantic code retrieval и editing
- BSL support через `bsl_language_server.py`
- MCP server implementation
- Интеграция с Claude Code, VSCode, Cursor

---

## Шаги

### 52.1 Скопировать Serena

```bash
cp -r D:/1C-Enterprise_Framework/serena tools/serena
```

Serena имеет собственный venv — скопировать или пересоздать.

### 52.2 Настроить venv

```bash
cd tools/serena
python -m venv .venv
.venv/Scripts/pip install -e .
```

Или если есть `requirements.txt`:
```bash
.venv/Scripts/pip install -r requirements.txt
```

### 52.3 Зарегистрировать в .mcp.json

```json
"serena": {
  "command": "D:\\1С-Framework\\tools\\serena\\.venv\\Scripts\\serena.exe",
  "args": ["start-mcp-server", "--context", "ide-assistant"],
  "cwd": "D:\\1С-Framework\\tools\\serena",
  "timeout": 180000,
  "initTimeout": 180000
}
```

### 52.4 Настроить BSL Language Server

Скопировать `bsl_language_server.py` из src/:
```bash
cp D:/1C-Enterprise_Framework/src/bsl_language_server.py tools/serena/
```

Настроить Serena для работы с BSL:
- Language ID: `bsl`
- Server: `bsl_language_server.py`
- Capabilities: symbols, definitions, references

### 52.5 Тестирование

- Symbol extraction для Python файла -> процедуры/функции
- Symbol extraction для BSL файла -> процедуры/функции
- Go to definition
- Find references

---

## Чеклист завершения

- [ ] `tools/serena/` содержит все файлы
- [ ] venv создан и работает
- [ ] `serena.exe start-mcp-server` запускается
- [ ] `.mcp.json` содержит `serena`
- [ ] BSL Language Server настроен
- [ ] Symbol extraction работает для Python и BSL
- [ ] Git commit: `feat: Phase 52 — Serena LSP Integration`
