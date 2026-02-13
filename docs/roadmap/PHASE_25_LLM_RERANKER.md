# Phase 25: LLM Reranker (Claude via Z.AI)

**Приоритет:** ВЫСОКИЙ | **Квартал:** Q1 2026 | **Версия:** v0.16.0
**Статус: РЕАЛИЗОВАНО**

> Оригинальная Phase 25 (MCP Native & Tool Integration) перенумерована в Phase 26.
> Подробности: [PHASE_26_MCP_INTEGRATIONS.md](PHASE_26_MCP_INTEGRATIONS.md)

---

## Проблема

CrossEncoder reranking на CPU занимает 60-120 секунд на запрос — основное узкое место пайплайна поиска. Модель `BAAI/bge-reranker-v2-m3` плохо понимает русскоязычный контекст 1С.

## Решение

Заменить CrossEncoder на Claude LLM reranker через Z.AI API:
- Отправляем запрос + до 20 чанков (по 800 символов)
- Claude оценивает каждый фрагмент по релевантности (0.0–1.0)
- Возвращаем отсортированные top_k результатов

## Реализовано

### 1. LLMReranker (`src/pdf_framework/search/reranking/llm_reranker.py`)

Новый класс с тем же интерфейсом `async rerank(query, results, top_k)`:

```python
class LLMReranker:
    def __init__(self, api_key, base_url, model, max_tokens=1024, temperature=0.0)
    async def rerank(query, results, top_k=5) -> list[SearchResult]
```

**Особенности:**
- Системный промпт на русском — эксперт по оценке релевантности
- JSON-ответ: `[{"index": 0, "score": 0.95}, ...]`
- Парсинг с fallback: если JSON не распознан — сохраняем оригинальный порядок
- `getattr(block, "text")` для извлечения текста из ContentBlock
- Lazy-init AsyncAnthropic клиента

### 2. Конфигурация (`src/pdf_framework/config.py`)

Новые поля в `AgentSettings`:
```python
reranker_type: Literal["cross_encoder", "llm"] = "llm"
reranker_llm_model: str = "claude-sonnet-4-5-20250929"
```

### 3. SearchManager (`src/pdf_framework/search/manager.py`)

Новый метод `_create_reranker()` — фабрика по `reranker_type`:
- `"llm"` → `LLMReranker(api_key, base_url, model)`
- `"cross_encoder"` → `CrossEncoderReranker(model_name)`

### 4. TwoStagePipeline (`src/pdf_framework/search/pipelines/two_stage.py`)

Тип `reranker` расширен до `Any` для совместимости обоих реализаций.

## Переключение

```bash
# LLM reranker (по умолчанию)
AGENT__RERANKER_TYPE=llm
AGENT__RERANKER_LLM_MODEL=claude-sonnet-4-5-20250929

# CrossEncoder (локальная модель)
AGENT__RERANKER_TYPE=cross_encoder
AGENT__RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

## Результаты тестирования

### Синтетический тест (5 чанков)
- Время: **2.65 сек** (цель: 1-3 сек)
- Качество: 3/3 релевантных чанка в top-3

### Live тест (hybrid search, 20 чанков)
- С реранкингом: **12.56 сек** (поиск 7.31 + реранкинг 5.25)
- Без реранкинга: **7.31 сек**
- Overhead реранкинга: **5.25 сек** (было 60-120 сек)
- Ускорение: **12-24x**

### Качество
- Переранжирование корректное: LLM поднял самый релевантный чанк с #2 на #1
- Оценки осмысленные: 0.38, 0.19, 0.13 (вместо сырых RRF 0.013)
- Понимание русского текста значительно лучше CrossEncoder

## Изменённые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/search/reranking/llm_reranker.py` | **НОВЫЙ** — LLM reranker |
| `src/pdf_framework/config.py` | `reranker_type`, `reranker_llm_model` |
| `src/pdf_framework/search/manager.py` | `_create_reranker()` фабрика |
| `src/pdf_framework/search/pipelines/two_stage.py` | reranker тип → `Any` |
| `.env` | `AGENT__RERANKER_TYPE=llm` |
| `.env.example` | Документация конфигурации |

## Сравнение

| Параметр | CrossEncoder | LLM Reranker |
|----------|-------------|--------------|
| **Время** | 60-120 сек | 5 сек |
| **CPU** | 100% загрузка | 0% |
| **Русский язык** | Слабо | Отлично |
| **Контекст** | Базовый | Глубокий (Claude) |
| **Стоимость** | Бесплатно (CPU) | ~$0.002/запрос |
| **Offline** | Да | Нет (API) |
