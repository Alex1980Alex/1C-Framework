# GLM-5.1 + Claude Code CLI — интеграция через Z.AI Anthropic-compatible endpoint (2026-05)

**Last verified:** 2026-05-01
**Domain:** developer-tools / claude-code / llm-routing
**Cross-ref:** `scripts/claude-backend/` (локальный switcher, commit `de6dd82a`)

---

## TL;DR

Z.AI — единственный провайдер кроме Anthropic, который выставляет **Anthropic-compatible API endpoint**, поэтому GLM-5.1 работает в Claude Code как drop-in replacement. Подключение = 2 переменные окружения + 3 model-mapping переменных в `~/.claude/settings.json` (секция `env`).

---

## Базовая конфигурация — **официальная (Z.AI docs, 2026-05-01)**

Источник: <https://docs.z.ai/scenario-example/develop-tools/claude>. Это **первоисточник** — блоги (CometAPI, aimadetools) указывают `glm-5.1` / `glm-5-turbo`, но официальная страница Z.AI на дату проверки приводит **только `glm-4.7` / `glm-4.5-air`**:

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "your_zai_api_key",
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "ANTHROPIC_DEFAULT_OPUS_MODEL":   "glm-4.7",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-4.7",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL":  "glm-4.5-air",
    "API_TIMEOUT_MS": "3000000"
  }
}
```

> Дословно из docs.z.ai: «The default model for GLM Coding Plan has been upgraded to GLM-4.7. Manual model adjustment is generally not recommended».

## GLM-5.1 — статус строк моделей

- **Третьеcторонние блоги** (CometAPI, aimadetools, viblo.asia, yaohanchen) предлагают `glm-5.1` / `glm-5-turbo` как валидные значения для `ANTHROPIC_DEFAULT_*_MODEL`.
- **Официальная Z.AI documentation** на 2026-05-01 их **не подтверждает** — только GLM-4.7 / GLM-4.5-Air.
- **Локальный `setup-zai.ps1`** проекта использует `ValidateSet("glm-5","glm-4.7","glm-4.7-air")` — это значит, что внутренний alias `glm-5` мог быть валидным где-то между релизами, но **не подтверждён** официальной страницей сегодня.

**Практический вывод:** для гарантированной работы — оставлять `glm-4.7` (как в официальной доке). Если хочется попробовать GLM-5.1 — менять руками после проверки, что Z.AI приняли строку (через `/status` или 401/400 от API). Не считать `glm-5.1` каноничным значением до обновления docs.z.ai.

## Прочие важные моменты

- `ANTHROPIC_AUTH_TOKEN` (НЕ `ANTHROPIC_API_KEY`) — Z.AI требует auth-token-форму.
- Endpoint `https://api.z.ai/api/anthropic` — Anthropic-compatible (Messages API), а не OpenAI-style.
- Интерфейс Claude Code продолжит показывать имена `claude-*`, но реально серверная сторона маппит их на GLM по `*_MODEL` переменным.
- API-ключ получают через **Z.AI Open Platform** (`https://z.ai/model-api`) → API Keys management.
- Рекомендованная версия Claude Code (по официальной доке): **2.0.14**.
- Чтобы вернуться к GLM-default — просто удалить `*_MODEL` строки из `settings.json` (auto-mapping останется).

## Тарификация / квота

GLM-5.1 и GLM-5-Turbo списываются из квоты GLM Coding Plan с множителем **3× в peak hours** и **2× off-peak**. Промо-период до конца июня 2026: 1× в off-peak. Подписка GLM Coding Plan начинается от ~$18/месяц.

## Локальный switcher проекта

В репо уже есть готовый инструмент (commit `de6dd82a`):

```powershell
# Первичная настройка (один раз)
cd scripts\claude-backend
.\setup-zai.ps1 -ApiKey "<ZAI_API_KEY>" -Model "glm-5.1"

# Переключение туда-обратно
.\switch-claude-backend.ps1 -Backend zai        # включить GLM
.\switch-claude-backend.ps1 -Backend anthropic  # вернуться на оригинал
```

`switch-claude-backend.ps1` делает backup `settings.json` в `~/.claude/backups/`, сохраняет ключи Z.AI в `zai-config.json` (gitignore-фикс уже в `.gitignore`).

> **Open task** — обновить `setup-zai.ps1`:
> - `ValidateSet` сейчас `"glm-5","glm-4.7","glm-4.7-air"` → добавить `"glm-5.1","glm-5-turbo"`.
> - `$haikuModel = "glm-4.5-air"` — оставить.
> - Default `-Model` → `"glm-5.1"`.

## Проверка после запуска

```powershell
claude          # запустить CLI
/status         # должен показать GLM-5.1 в текущем slot'е модели
```

Если `/status` всё ещё показывает Anthropic — проверь `~/.claude/settings.json` (env-секция перезаписана?), перезапусти shell для пере-инжекции env-переменных.

## Ограничения / known issues

- **GitHub Actions** (`anthropics/claude-code-action`) официально **не поддерживает** custom `ANTHROPIC_BASE_URL` — issue/discussion #673. Только локальный CLI.
- Tools/agents/MCP, которые делают прямые вызовы к Anthropic SDK с собственным ключом, **не маршрутизируются** через GLM — нужно править их env отдельно.
- Streaming: Z.AI поддерживает Anthropic streaming format, но ряд edge-кейсов (cache_control блоки, prompt caching) может вести себя иначе — для cache-heavy сценариев тестировать отдельно.

## Связано в проекте

- `scripts/claude-backend/README.md` — quick-start, model table, безопасность.
- `src/shared/llm_rotation/` — production-альтернатива (5 провайдеров, fallback) вместо ручного switcher.
- Skill `llm-rotation` — когда использовать ротацию.
- Skill `claude-code-settings` — общий контекст по `settings.json` scopes.

## Sources

- [Claude Code — Z.AI Developer Documentation](https://docs.z.ai/devpack/tool/claude)
- [How to Use Z.AI in Claude Code — ClaudeLog](https://claudelog.com/faqs/how-to-use-z-ai-in-claude-code/)
- [GLM-5.1 + Claude Code Guide (2026): Setup, Benchmarks, Cost — CometAPI](https://www.cometapi.com/how-to-use-glm-5-1-with-claude-code/)
- [Run Claude Code with GLM-5.1 for $18/Month — Setup Guide (aimadetools)](https://www.aimadetools.com/blog/glm-5-1-claude-code-setup/)
- [Z.ai API Complete Guide — GLM Models, Pricing, and Setup (2026)](https://www.aimadetools.com/blog/z-ai-api-complete-guide/)
- [GitHub: ankurkakroo2/claude-code-glm-setup](https://github.com/ankurkakroo2/claude-code-glm-setup)
- [Anthropic API format for GLM Coding Plan — aiengineerguide](https://aiengineerguide.com/til/anthropic-api-format-glm-coding-plan/)
- [Claude Code GitHub Actions + Z.AI discussion #673](https://github.com/anthropics/claude-code-action/discussions/673)
- [GLM Coding Plan — z.ai/subscribe](https://z.ai/subscribe)
