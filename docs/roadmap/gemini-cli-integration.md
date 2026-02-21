# Дорожная карта интеграции Gemini CLI

**Цель:** Обеспечить работу Google Gemini (через Vertex AI или AI Studio) в рамках существующего `1С-Framework`.
**Принцип:** Максимальная изоляция интеграционных файлов. Gemini CLI не должен зависеть от конфигурации или файлов внутри папки `.claude`. Общая логика и знания выносятся в нейтральные директории.

## Фаза 1: Подготовка окружения (Environment)
- [ ] **Аутентификация Google Cloud**
  - [ ] Получить API Key (AI Studio) или настроить Vertex AI.
  - [ ] Установить `gcloud CLI` и выполнить `gcloud auth application-default login` (для Vertex AI).
  - [ ] Добавить переменные окружения: `GOOGLE_API_KEY`, `GCP_PROJECT_ID`, `GCP_REGION`.
- [ ] **Обновление Python Virtual Environment**
  - [ ] Активировать текущий venv: `.venv\Scripts\activate`.
  - [ ] Установить SDK: `pip install google-generativeai langchain-google-genai`.
  - [ ] Установить CLI инструмент (например, `deepagents`): `pip install deepagents`.
  - [ ] Обновить `requirements.txt`.

## Фаза 2: Архитектурная изоляция (Shared Core)
- [ ] **Рефакторинг Хуков (Shared Logic)**
  - [ ] Создать нейтральную директорию для логики: `D:\1С-Framework\core\hooks\` (или `shared/hooks`).
  - [ ] Выделить бизнес-логику из `.claude/hooks/*.py` в модули внутри `core`.
  - [ ] Обновить хуки Claude (`.claude/hooks/*.py`), чтобы они импортировали логику из `core`.
- [ ] **Структура Gemini**
  - [ ] Создать изолированную директорию проекта: `D:\1С-Framework\.gemini\` (или `.deepagents`).
  - [ ] Создать независимый файл конфигурации (например, `.gemini/config.json`).
- [ ] **Адаптеры Хуков (Gemini Hooks)**
  - [ ] Создать хуки в `.gemini/hooks/`, специфичные для событий Gemini CLI.
  - [ ] Реализовать вызов общей логики из `core` внутри этих хуков.
  - [ ] *Результат:* Логика (например, роутинг задач) едина, но точки входа (файлы интеграции) полностью разделены.

## Фаза 3: Нейтрализация Знаний (Skills & Memory)
- [ ] **Миграция Скиллов**
  - [ ] Переместить скиллы из `.claude/skills` в нейтральную директорию `D:\1С-Framework\shared\skills`.
  - [ ] Создать Symlink: `.claude/skills` -> `shared/skills` (для обратной совместимости).
  - [ ] Создать Symlink: `.gemini/skills` -> `shared/skills`.
- [ ] **Общая Память**
  - [ ] Определить нейтральное место для памяти (например, `D:\1С-Framework\docs\memory`).
  - [ ] Настроить оба CLI на использование этого пути для чтения/записи контекста.

## Фаза 4: Тестирование и Валидация
- [ ] **Unit-тесты Core**
  - [ ] Проверить, что логика в `core/hooks` работает независимо от контекста Claude/Gemini.
- [ ] **Интеграционный тест Gemini**
  - [ ] Запустить Gemini CLI и проверить работу скиллов из `shared/skills`.
  - [ ] Проверить срабатывание хуков из `.gemini/hooks`.
- [ ] **Сравнение качества (Benchmark)**
  - [ ] Сравнить ответы Claude 3.7 и Gemini 1.5 Pro на одних и тех же задачах.

## Фаза 5: Автоматизация (Optional)
- [ ] Создать `start-gemini.bat` и `start-claude.bat`.
- [ ] Настроить единый логгер (Tracer) в `core`, чтобы оба инструмента писали логи в один формат.