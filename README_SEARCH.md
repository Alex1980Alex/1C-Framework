# PDF Search - Usage Guide

## 🎯 Best Practice: Use Through Claude Code

The most reliable way to use PDF search is through Claude Code's assistant interface.

## How It Works

### 1. Ask Claude to Search

Simply say:
```
Найди информацию про "установку 1С"
```

Claude will:
1. Execute `python search_json.py "ваш запрос"`
2. Read results from `data/search_output.json`
3. Format and display results beautifully in chat

### 2. Available Commands

**Search:**
```
Найди в документах "ваш запрос"
```

**Get Statistics:**
```
Покажи статистику индекса
```

**Index New PDF:**
```
Проиндексируй файл data/pdfs/новый.pdf
```

## 📊 Output Format in Chat

Claude will show:

```markdown
## Поиск: "ваш запрос"

**Найдено:** 3 результата за 6.5 секунд
**Стратегия:** vector search

---

### [1] Релевантность: 0.624

**Источник:** Документ `abc123`, chunk #5

[Full content displayed here...]

---

### [2] Релевантность: 0.577

**Источник:** Документ `abc123`, chunk #7

[Full content displayed here...]
```

## 🔧 Technical Details

### Pattern Used

Based on analysis of 5+ GitHub projects:

1. **rag-chunk** - Table-based output
2. **MCP Vector Search** - CLI-first with rich output
3. **refer** - Multiple output formats
4. **SemTools** - LlamaIndex CLI patterns
5. **Rich Library** - Professional terminal formatting
6. **LangChain** - Best practices for source attribution

### Implementation

- **search_json.py** - Core search script (Windows-compatible)
- **search_helper.py** - Python API for programmatic access
- **pdf_search.py** - Full-featured CLI with Rich (for Unix/WSL)

### Why This Approach?

- ✅ No encoding issues on Windows
- ✅ Clean, formatted output in chat
- ✅ Full metadata and source attribution
- ✅ Interactive conversation flow
- ✅ Works reliably every time

## 📝 Examples

### Search Example

**You:** Найди про "конфигурацию и платформу"

**Claude:** [Executes search and formats results]

### Stats Example

**You:** Покажи статистику

**Claude:**
```
Статистика индексации:
- Vector Store: 31 chunks
- Graph Store: 0 nodes, 0 edges
```

## 🚀 Next Steps

After setup:
1. Add more PDFs to `data/pdfs/`
2. Ask Claude to index them
3. Search freely using natural language

The framework handles all technical details automatically!
