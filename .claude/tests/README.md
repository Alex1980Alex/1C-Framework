# Code Skill Enforcer - Test Suite

Тестовый набор для хука принудительного использования скиллов.

## Структура

```
.claude/tests/
├── test_code_skill_enforcer.py  # Unit tests (15 tests)
├── test_integration.py           # Integration tests (6 flows)
├── test_e2e.py                   # E2E scenarios (3 scenarios)
├── run-all-tests.py              # Test runner
└── README.md                     # This file
```

## Запуск тестов

### Все тесты

```bash
cd D:/1С-Framework
python .claude/tests/run-all-tests.py
```

### Отдельные suites

```bash
# Unit tests
python .claude/tests/test_code_skill_enforcer.py

# Integration tests
python .claude/tests/test_integration.py

# E2E scenarios
python .claude/tests/test_e2e.py
```

### С pytest

```bash
pytest .claude/tests/ -v
pytest .claude/tests/test_code_skill_enforcer.py -v
```

## Описание тестов

### Unit Tests (15)

Уровни enforcement:
- **A**: Content patterns (StateGraph → langgraph-core)
- **B**: Directory rules (.claude/hooks/ → create-hook)
- **C**: Bash commands (docker compose → deployment)
- **D**: Research cache reminder
- **E**: Post-verification
- **F**: LEARN phase

Edge cases:
- Wrong tool (Read)
- Empty content
- Short content (< 20 chars)
- Malformed JSON
- Missing tool_name

### Integration Tests (6)

Полные workflows:
1. **PRE-A flow**: BLOCK → activate → ALLOW
2. **PRE-B flow**: hooks/ directory → create-hook → ALLOW
3. **PRE-C flow**: docker → deployment → ALLOW
4. **Research flow**: FastAPI → research protocol → pending_learn
5. **POST-E flow**: Activated skill → verification → advisory
6. **LEARN flow**: Research → Write → 3 tasks

### E2E Scenarios (3)

1. **Full PRE Cycle**: Prompt → Read → Write → BLOCK → Skill → retry → OK
2. **Full LEARN Cycle**: New library → research → apply → tasks → create skill
3. **Cross-Session**: Session 1 LEARN → Session 2 fast path

## Покрытие

| Тип | Кол-во | Покрытие |
|-----|--------|----------|
| Unit tests | 15 | Уровни A-F + edge cases |
| Integration | 6 | Complete workflows |
| E2E | 3 | Real-world scenarios |
| **Итого** | **24** | **78% roadmap** |

## Требования

- Python 3.8+
- Хук: `.claude/hooks/code-skill-enforcer.py`
- Модули: `base/`, `shared/`
- Config: `.claude/hooks/shared/code-skill-patterns.json`

## Автор

Claude Code
Дата: 2026-02-23
Версия: 1.0.0
