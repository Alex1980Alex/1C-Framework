---
name: auto-test-after-write
description: "Автозапуск проверки синтаксиса и тестов после записи BSL модуля через MCP"
type: skill
category: testing
triggers:
  - event: "after:write_module_source"
autoApply: true
language: bsl
tags:
  - testing
  - bsl-only
  - metr-integration
version: "1.0.0"
created: 2026-03-31
---

# Auto-Test After Write

## Назначение

Автоматически запускает проверку синтаксиса и юнит-тесты после записи BSL модуля через `write_module_source`.

## Workflow

### 1. Проверка синтаксиса

```python
mcp__metr__check_syntax_designer_config(
  config_path="./src/configuration",
  target_module="{module_name}",
  check_type="designer"
)
```

**Если ошибки** -> STOP, показать ошибки, ждать исправления.
**Если OK** -> продолжить к тестам.

### 2. Поиск связанных тестов

```python
mcp__serena__find_symbol(
  name_path="{module_name}Test",
  relative_path="src/",
  include_body=false
)
```

Паттерны: `{Module}Test`, `{Module}Tests`, `{Category}IntegrationTest`

### 3. Запуск тестов

```python
mcp__metr__run_tests(
  config_path="./src/configuration",
  test_framework="YaXUnit",
  filter={
    "include_modules": [discovered_tests],
    "timeout_per_test_sec": 30
  },
  parallel_workers=2,
  fail_fast=false
)
```

### 4. Отчёт

```
AUTO-TEST: {ModuleName}
[OK] Синтаксис: 0 ошибок (0.25s)
[OK] Тесты: 12/12 (1.45s)
Статус: READY FOR COMMIT
```

## Ограничения

- Только BSL модули (не Python/JS)
- Требует METR (`mcp-yaxunit-runner-0.5.1.jar`)
- Требует YaXUnit extension в конфигурации
