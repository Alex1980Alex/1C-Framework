# Pipeline (compact) — LLM Rotation: sonnet-first primary order

**Класс:** trivial (config/docs, изменение порядка провайдеров по решению пользователя)
**Дата:** 2026-07-04

## Планирование
Пользователь: первым должен вызываться `claude-cli-sonnet` (claude-sonnet-5), дальше по списку.
Развилка (AskUserQuestion) → выбор «Код + убрать zai-glm5 из .mcp.json».

## Дизайн
Сменить primary `claude-cli-haiku` → `claude-cli-sonnet` в трёх слоях:
код-дефолт (`config.py`), порядок (`service.py::DEFAULT_PROVIDERS`), рантайм-override (`.env`).
Синхронизировать таблицы доков 21.1/21.8/15.1/15.4 + SKILL.md. Убрать фантомную ноту про
`.mcp.json`-override `zai-glm5` (ключа там нет — только `ZAI_API_KEY` + `LLM_ROTATION_TIMEOUT`).

## Кодирование
- `config.py`: primary_provider → claude-cli-sonnet + докстринг
- `service.py`: DEFAULT_PROVIDERS reorder (sonnet=0, haiku=1)
- `.env:12`: LLM_ROTATION_PRIMARY_PROVIDER=claude-cli-sonnet
- доки 21.1/21.8/15.1/15.4 + SKILL.md: таблицы + env-примеры
- роадмап 260704 P0.4: ✅ DONE

## Тестирование / верификация
Рантайм-смоук (свежий процесс + `.env`): primary=claude-cli-sonnet, порядок sonnet→haiku→ollama→anthropic,
таймауты 90/120/240. 4 ассерта существующих тестов `test_llm_rotation.py` реплеем — PASS.
⚠ MCP-сервер требует `/mcp reconnect`.
