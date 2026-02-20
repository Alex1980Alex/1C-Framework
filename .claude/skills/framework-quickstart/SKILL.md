# Framework Quickstart

## Когда использовать
- "установка", "install", "начать", "start", "первый запуск"
- "quickstart", "getting started", "системные требования"
- "как запустить", "развернуть с нуля", "настроить окружение"

---

## Системные требования

| Требование | Минимум | Рекомендуется |
|-----------|---------|---------------|
| **Python** | 3.11 | 3.11+ |
| **RAM** | 8 GB | 16+ GB |
| **Диск** | 5 GB | 20+ GB (для моделей и индексов) |
| **Docker** | Docker Desktop | Docker Desktop + Docker Compose |
| **GPU** | Не обязательно | NVIDIA GPU (CUDA) для ускорения embeddings |
| **ОС** | Windows 10+, Linux, macOS | Windows 11, Ubuntu 22.04+ |

---

## Установка (5 шагов)

### 1. Клонирование и venv

```bash
git clone <repository-url> 1C-Framework
cd 1C-Framework

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 2. Установка зависимостей

```bash
# Все зависимости
pip install -e ".[all]"

# Или через Makefile
make install
```

Установка по группам:

| Группа | Команда | Что включает |
|--------|---------|-------------|
| Ядро | `pip install -e .` | Без UI, без evaluation |
| GPU | `pip install -e ".[gpu]"` | + CUDA ускорение |
| Eval | `pip install -e ".[eval]"` | + RAGAS, evaluation |
| Prod | `pip install -e ".[prod]"` | + production зависимости |
| Всё | `pip install -e ".[all]"` | Полная установка |

### 3. Запуск Qdrant (Docker)

```bash
docker run -d --name qdrant \
    -p 6333:6333 -p 6334:6334 \
    -v $(pwd)/data/qdrant_storage:/qdrant/storage \
    qdrant/qdrant:v1.15.5

# Проверка
curl http://localhost:6333/healthz
```

### 4. Настройка .env

```bash
cp .env.example .env
# Обязательно указать:
# ANTHROPIC__API_KEY=your-anthropic-api-key
```

Подробная настройка → `framework-config`

### 5. Проверка

```bash
python -m src.cli.main --help
curl http://localhost:8000/health
```

---

## Альтернатива: Docker Compose (всё одной командой)

```bash
cp .env.example .env
# Отредактировать .env — указать ANTHROPIC__API_KEY

docker compose -f docker/docker-compose.yml up -d
# → Qdrant (порт 6333) + API (порт 8000) + UI (порт 7860)
```

---

## Первый запуск: 3 пути

### Путь A: CLI (рекомендуется)

```bash
# 1. Запустить API
python -m src.api.app

# 2. Индексировать PDF
python -m src.cli.main index "data/pdfs/your-document.pdf" --graph

# 3. Поиск
python -m src.cli.main search "конфигуратор" --strategy hybrid

# 4. RAG вопрос
python -m src.cli.main ask "Что такое конфигуратор?" --stream
```

### Путь B: Python API (QuickRAG — 3 строки)

```python
from src.pdf_framework import QuickRAG

rag = QuickRAG()
rag.add("data/pdfs/your-document.pdf")
answer = rag.ask("Что такое конфигуратор?")
print(answer)
```

### Путь C: Web UI

```bash
# API
python -m src.api.app
# UI (в отдельном терминале)
python -m src.ui.app
# Открыть http://localhost:7860
```

1. Вкладка **Documents** → загрузить PDF
2. Вкладка **Search** → поиск
3. Вкладка **Chat** → вопрос-ответ

---

## Что происходит при индексации

```
PDF → Hybrid Loader (PyMuPDF + Docling + Vision OCR)
  → Splitting (~500-800 символов)
  → Embedding (E5-large, 1024d)
  → Qdrant (dense + BM25 sparse vectors)
  → BM25 FTS5 (русская лемматизация)
  → (--graph) Граф знаний (entities + relations)
```

---

## Частые проблемы при установке

| Проблема | Решение |
|----------|---------|
| `pip install` падает на `sentence-transformers` | `pip install torch` отдельно, затем повторить |
| Docker не запускается | Убедитесь, что Docker Desktop запущен |
| `CUDA not available` | `pip install torch --index-url https://download.pytorch.org/whl/cu121` |
| Qdrant недоступен | `docker ps` — проверить, что контейнер запущен |
| `ModuleNotFoundError` | Убедитесь, что venv активирован |

---

## Что дальше

| Задача | Скилл |
|--------|-------|
| Настроить .env параметры | `framework-config` |
| Изучить CLI команды | `framework-cli` |
| Выбрать стратегию поиска | `search-pipeline-debug` |
| Настроить индексацию | `indexing-pipeline` |
| REST API интеграция | `framework-api` |
| MCP / Web UI / Python API | `framework-mcp-ui` |

## Файлы
- API: `src/api/app.py`
- CLI: `src/cli/main.py`
- UI: `src/ui/app.py`
- MCP: `src/mcp_server/server.py`
- Docker: `docker/docker-compose.yml`
