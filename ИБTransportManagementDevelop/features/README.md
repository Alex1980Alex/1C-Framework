# Vanessa BDD Tests — ИБTransportManagementDevelop

`.feature` файлы для UI/integration тестов через Vanessa Automation.

## Структура

```
features/
  README.md                                  (этот файл)
  <feature-name>.feature                     ← .feature файлы (gherkin)
  <subsystem>/                                ← логически сгруппированные тесты
    <scenario>.feature
```

## Конвенция именования

- Имена файлов — на латинице, kebab-case: `transport-blocking.feature`,
  `unloading-direction-creation.feature`
- Сценарии внутри — на русском (gherkin поддерживает Cyrillic ключевые слова)

## Запуск

### Все тесты задачи

```powershell
..\tools\vanessa\run-bdd.ps1 -OutputJson -RunId <jira-ticket>
```

### Конкретный .feature

VS Code: открыть `.feature` → `Tasks: Run Task → Vanessa BDD: прогон тестов задачи (текущий .feature)`.

## Pre-scenario TestDB check (MANDATORY)

Перед написанием каждого .feature — проверить наличие тестовых данных
в TestDB через `mcp__1c-mcp-crud__execute_query`. Подробнее — в skill
`va-bdd-testing` v1.1 Stage 4a.

## Resume и .run-state.json

Прогон через `run-bdd.ps1` поддерживает chained execution с resume:
- При прерывании создаётся `.run-state.json` (в gitignore)
- Повторный запуск продолжает с failed-сценария

## Калибровка шагов

Калиброванные паттерны шагов (CheckBox, RadioButton, SpinEdit, Date,
CompositeType, ARM forms, DynamicList tables, кнопки документов) —
в skill `va-bdd-testing` (раздел «Form controls»).
