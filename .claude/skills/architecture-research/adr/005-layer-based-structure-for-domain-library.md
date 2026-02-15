# ADR-005: Layer-based структура для domain library

**Статус:** accepted
**Дата:** 2026-02-12
**Исследование:** [../cache/project-structure-best-practices.md](../cache/project-structure-best-practices.md)

---

## Контекст

Проект PDF Vector & Graph Framework вырос до 251 Python-файла с 4 точками входа (API, CLI, MCP, UI) и 19 пакетами в ядре `pdf_framework/`. Необходимо определить, правильно ли организована текущая структура и какие улучшения нужны.

Исследованы два подхода:
- **Layer-based** (по техническому слою): loaders/, search/, agents/, vector_store/
- **Feature-based** (по домену): auth/, users/, posts/ — каждый со своими router, model, schema

---

## Решение

**Сохранить layer-based организацию** для `pdf_framework/` (ядро) и добавить **Service Layer** в `api/`.

### Обоснование

1. `pdf_framework/` — это **domain library** (не бизнес-приложение). Layer-based подходит для библиотек, feature-based — для приложений с множеством бизнес-доменов.

2. У нас **один домен** (PDF RAG), поэтому feature-based не даёт преимуществ — нечего разделять на бизнес-фичи.

3. Текущая структура **на 85% соответствует best practices**: interface-based design, strategy pattern, async-first, нет циклических зависимостей.

### Конкретные действия

| Приоритет | Действие | Обоснование |
|-----------|----------|-------------|
| Средний | Добавить `api/services/` (Service Layer) | Разделить routes и framework (Clean Architecture) |
| Средний | Разбить `Components` на domain-specific holders | Устранить God Object anti-pattern |
| Низкий | Удалить deprecated файлы в `loaders/` | Техдолг (дублирование image/table extractors) |
| Низкий | Удалить пустые пакеты (6 шт.) | Техдолг |
| Отложено | UV Workspaces | Только при росте >500 файлов или необходимости независимого версионирования |

---

## Последствия

### Положительные
- Подтверждена правильность текущей архитектуры (не нужна радикальная перестройка)
- Service Layer улучшит тестируемость API
- Разбиение Components упростит DI и снизит coupling

### Отрицательные
- Service Layer добавит слой indirection (3-5 файлов)
- Разбиение Components требует рефакторинга `api/routes/` (16 файлов)

### Нейтральные
- Не нужен переход на UV Workspaces на текущем масштабе
- Feature-based организация не нужна при одном домене

---

## Альтернативы

1. **Полный переход на feature-based** — отклонено: один домен (PDF RAG), нечего разбивать по бизнес-фичам
2. **UV Workspaces (монорепо)** — отложено: текущий pyproject.toml справляется, переход оправдан при >500 файлах
3. **Hexagonal Architecture (полная)** — отклонено: чрезмерно для текущего масштаба; частичная реализация (Service Layer) достаточна
4. **Ничего не менять** — отклонено: God Object в Components и tight coupling в routes — реальные проблемы
