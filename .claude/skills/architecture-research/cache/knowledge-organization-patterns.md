# Knowledge Organization Patterns — разделение фактов и решений

**Дата:** 2026-02-14
**Статус:** актуально
**Теги:** [knowledge-management, zettelkasten, adr, architecture-decision-records, atomic-notes, google-adk, kba]

---

## 1. Из документации (docs/documentation/)

### Claude Code Memory ([Управление памятью Claude.md](docs/documentation/Claude%20Code%20Docs/3.%20Конфигурация/Управление%20памятью%20Claude.md))

- 5 уровней памяти: Enterprise Policy → Project Memory → Project Rules → User Memory → Local Project Memory
- `.claude/rules/` — модульные правила по темам, каждый файл `.md` охватывает одну тему
- Path-specific rules через YAML frontmatter `paths:` — условная загрузка по glob-паттернам
- Подкаталоги поддерживаются: `rules/frontend/`, `rules/backend/`
- Символические ссылки для шаринга между проектами
- Принцип: "Каждый файл должен охватывать одну тему"

### Расширение с помощью навыков ([Расширение Claude с помощью навыков.md](docs/documentation/Claude%20Code%20Docs/2.%20Создавайте%20с%20Claude%20Code/Расширение%20Claude%20с%20помощью%20навыков.md))

- Файл пустой (1 строка) — документация не загружена

---

## 2. Из интернета

### Zettelkasten — принцип атомарности [web]

Источник: [Zettelkasten.de — The Building Blocks of a Zettelkasten](https://zettelkasten.de/posts/building-blocks-zettelkasten/)

- 6 типов блоков знаний (building blocks):
  1. **Concepts** — определения и объяснения
  2. **Arguments** — обоснования
  3. **Counter-arguments** — контраргументы
  4. **Models** — фреймворки мышления
  5. **Hypotheses** — предположения
  6. **Empirical observations** — наблюдения/факты
- **Принцип атомарности**: одна заметка = одна идея
- Наблюдения (факты) и выводы (решения) — разные атомарные заметки
- Переиспользуемость: факт можно использовать в разных контекстах для разных выводов

### Architecture Decision Records (ADR) [web]

Источник: [joelparkerhenderson/architecture-decision-record](https://github.com/joelparkerhenderson/architecture-decision-record) (10k+ stars)

- Индустриальный стандарт документирования архитектурных решений
- Формат: **Context → Decision → Consequences → Alternatives**
- Жизненный цикл: Research → Evaluate → Decision → Implement → Sunset
- Статусы: proposed → accepted → superseded → deprecated
- MADR (Markdown ADR): [adr/madr](https://github.com/adr/madr) — популярный шаблон
- [andronics/claude-plugin-adr](https://github.com/andronics/claude-plugin-adr) — Claude-плагин для ADR

### Google ADK Memory Architecture [web]

Источник: Google Agent Development Kit documentation

- 3 уровня памяти:
  1. **Memory** — долгосрочные факты и предпочтения (persisted)
  2. **Working Context** — активные рассуждения (session-scoped)
  3. **Artifacts** — большие данные, версионированные по имени
- Факты и рассуждения — разные уровни хранения
- Artifacts именованы и версионированы — не смешиваются с фактами

### Knowledge-Based Agent (KBA) [web]

Источник: AI textbooks, Russell & Norvig

- **Knowledge Base** — хранённые факты (tell/ask interface)
- **Inference Engine** — механизм вывода решений из фактов
- Разделение позволяет менять правила вывода без потери фактов
- Аналогия: cache = Knowledge Base, ADR = результат Inference Engine

---

## 3. Ключевые источники

- [Zettelkasten.de — Building Blocks](https://zettelkasten.de/posts/building-blocks-zettelkasten/) — атомарность знаний
- [joelparkerhenderson/architecture-decision-record](https://github.com/joelparkerhenderson/architecture-decision-record) — ADR стандарт (10k+ stars)
- [adr/madr](https://github.com/adr/madr) — MADR шаблон
- [andronics/claude-plugin-adr](https://github.com/andronics/claude-plugin-adr) — Claude ADR plugin
- [Claude Code Memory Docs](docs/documentation/Claude%20Code%20Docs/3.%20Конфигурация/Управление%20памятью%20Claude.md) — иерархия памяти
- Google ADK Memory Architecture — 3-tier memory model
- Russell & Norvig, "Artificial Intelligence: A Modern Approach" — KBA pattern
