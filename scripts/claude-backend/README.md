# Claude Backend Switcher

Скрипты для переключения Claude Code между **Anthropic** и **Z.AI GLM**.

---

## Структура

```
scripts/claude-backend/
├── README.md                    # Этот файл
├── setup-zai.ps1                # Первоначальная настройка Z.AI
├── switch-claude-backend.ps1    # Переключение между backend'ами
└── zai-config.json              # Сохранённые настройки Z.AI (создаётся автоматически)
```

> **API key храним в `zai-config.json` в открытом виде.** Файл должен быть в `.gitignore`. Альтернатива — переменная окружения `ZAI_API_KEY` (см. §Безопасность).

---

## Шаг 1 — первоначальная настройка Z.AI (один раз)

```powershell
cd C:\1С-Framework\scripts\claude-backend
.\setup-zai.ps1 -ApiKey "ВАШ_API_КЛЮЧ_Z.AI"
```

**Опционально** — выбрать модель:

```powershell
.\setup-zai.ps1 -ApiKey "ВАШ_КЛЮЧ" -Model "glm-4.7-air"
```

| Модель | Скорость | Цена | Качество |
|--------|----------|------|----------|
| `glm-5` (default) | Средняя | $$ | Лучшее |
| `glm-4.7` | Средняя | $$ | Отличное |
| `glm-4.7-air` | Быстрая | $ | Хорошее |

Получить ключ: <https://z.ai/manage-apikey/apikey-list>.

---

## Шаг 2 — переключение между backend'ами

### На Anthropic (оригинал)

```powershell
.\switch-claude-backend.ps1 -Backend anthropic
claude
```

### На Z.AI GLM

```powershell
.\switch-claude-backend.ps1 -Backend zai
claude
```

---

## Что делают скрипты

### `setup-zai.ps1`

1. Сохраняет API-ключ Z.AI в `zai-config.json` (рядом со скриптом)
2. Обновляет `~/.claude/settings.json` — секция `env`:
   - `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`
   - `ANTHROPIC_AUTH_TOKEN=<ваш ключ>`
   - `ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-4.5-air`
   - `ANTHROPIC_DEFAULT_SONNET_MODEL=<выбранная модель>`
   - `ANTHROPIC_DEFAULT_OPUS_MODEL=<выбранная модель>`
3. Устанавливает соответствующие переменные окружения в текущей сессии

### `switch-claude-backend.ps1`

| Параметр | Что происходит |
|----------|----------------|
| `-Backend anthropic` | Сохраняет текущий Z.AI-конфиг → удаляет переменные из `settings.json` → возвращает оригинальный Anthropic API (использует `ANTHROPIC_API_KEY`) |
| `-Backend zai` | Восстанавливает Z.AI-конфиг из `zai-config.json` в `settings.json` |

**Автоматически:**
- Создаёт резервные копии `~/.claude/settings.json` в `~/.claude/backups/settings_<timestamp>.json` перед каждым переключением
- Сохраняет Z.AI-конфиг при возврате на Anthropic, чтобы потом можно было переключиться обратно без повторного `setup-zai.ps1`

---

## Запуск Claude Code с MCP-профилями

Существующий `scripts/claude.bat` поддерживает 4 MCP-профиля. После переключения backend'а:

```powershell
# Everyday — повседневная работа (PDF RAG)
claude --strict-mcp-config --mcp-config .mcp\pdf.json

# Full — все инструменты
claude --strict-mcp-config --mcp-config .mcp\full.json

# 1С Development
claude --strict-mcp-config --mcp-config .mcp\bsl.json

# Lazy MCP (auto-select)
claude --strict-mcp-config --mcp-config .mcp\lazy-mcp.json
```

Или интерактивно через `scripts\claude.bat`.

---

## Безопасность

`zai-config.json` содержит API-ключ в plain text. Рекомендации:

1. **Добавить в `.gitignore`:** `scripts/claude-backend/zai-config.json`
2. **Альтернатива — переменная окружения:**
   ```powershell
   [Environment]::SetEnvironmentVariable("ZAI_API_KEY", "<ваш ключ>", "User")
   ```
   Тогда Claude Code будет использовать ключ из env, и `zai-config.json` хранит только модельные настройки.
3. **Для production-окружений:** использовать `LLMRotationService` (`src/shared/llm_rotation/`) — он управляет 5 провайдерами с rotation/fallback и не требует ручного переключения.

---

## Связано

- `src/shared/llm_rotation/` — сервис ротации LLM (5 провайдеров)
- `scripts/claude.bat` — меню MCP-профилей
- `.mcp/*.json` — конфигурации MCP-серверов
- Skill `llm-rotation` — когда использовать ротацию вместо прямого backend switch
