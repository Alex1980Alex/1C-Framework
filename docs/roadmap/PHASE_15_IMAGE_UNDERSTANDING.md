# Phase 15: Image Understanding & Multimodal RAG

**Приоритет:** КРИТИЧЕСКИЙ | **Квартал:** Q1 2026 | **Версия:** v0.6.0
**Источники:** RAGFlow, Dify, LightRAG, Kotaemon
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Изображения в документации 1С содержат критически важную информацию:
диаграммы архитектуры, скриншоты интерфейсов, схемы бизнес-процессов, таблицы.
Без обработки изображений теряется значительная часть контента.

## Решение

Claude Vision API для описания изображений + индексация описаний вместе с текстом.

## Реализовано

| Шаг | Задача | Детали |
|-----|--------|--------|
| 15.1 | **Извлечение изображений** | PyMuPDF `extract_images=True`, min_size=50x50 |
| 15.2 | **Claude Vision описание** | claude-sonnet-4-5-20250929, max_tokens=2048 |
| 15.3 | **System prompt + few-shot** | `_SYSTEM_PROMPT` как OCR-транскриптор, `_TABLE_EXAMPLE` с `\|` форматом |
| 15.4 | **Image-aware chunking** | Привязка к странице через `page_number` |
| 15.5 | **Мультимодальный индекс** | 119 image chunks в Qdrant (dense + bm25 sparse) |
| 15.6 | **Markdown таблицы** | 97/119 (81.5%) содержат `\|`-формат |

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `src/pdf_framework/processing/image_extractor.py` | ImageExtractor с Vision API |
| `src/pdf_framework/embeddings/vision.py` | Vision embedding integration |
| `src/pdf_framework/config.py` | VisionSettings (model, max_tokens) |

## Результаты

- 119 image chunks из 1 PDF (Глава 5)
- Средняя длина описания: 1237 символов (max 2016)
- 97/119 (81.5%) содержат markdown таблицы
- 1/119 галлюцинация (page 41, 8K chars garbage) — единичный случай
- Large PDFs с 100+ изображениями: нужен timeout 1h+
