# Opus Architect + Sonnet Implementer — Claude Code multi-model workflows (May 2026)

**Last verified:** 2026-05-01
**Domain:** developer-tools / claude-code / multi-agent
**Cross-ref:** `.claude/agents/learning-loop.md` (existing opus subagent), `claude-code-subagents` skill

---

## TL;DR

В Max-плане Claude Code (Nov 2025+) Sonnet и Opus имеют **независимые квоты** — Sonnet не "съедает" Opus-бюджет и наоборот. Это открывает двухмодельный workflow: Opus = архитектор/ревьюер, Sonnet = реализатор. Три практических способа активировать:

1. **`/model opusplan`** — встроенный режим: Opus в plan mode, Sonnet в execution mode (одна команда, без файлов).
2. **Custom subagent с `model: sonnet`** — основная сессия Opus, делегирует через `Task(...)` подагенту-имплементеру.
3. **Advisor strategy** — Opus как non-executing адвайзер, Sonnet/Haiku как hands-on исполнитель, Opus ревьюит итерации.

---

## Раздельные квоты Max-плана

С 2025-11-24 Anthropic ввёл **independent Sonnet quota** на Max(5x/20x):

| Лимит | Что считается | Reset |
|---|---|---|
| `Current session` (5h rolling) | Все модели вместе | каждые 5 ч от первого запроса |
| `Weekly: All models` | Opus + Sonnet + Haiku суммарно | Sun 5:00 AM |
| `Weekly: Sonnet only` | **Только Sonnet** — отдельный пул | Sun 5:00 AM |
| `Daily included routine runs` | Бэкграунд-агенты (cron/schedule) | Daily |

**Practical impact**: можно гонять Sonnet-имплементера параллельно с Opus-архитектором без риска быстро исчерпать Opus-квоту. Значит делегирование объёмной работы Sonnet'у — реальная экономия Opus-токенов.

Caveat: support-doc Anthropic пишет "limits are shared across Claude and Claude Code" — формулировка устарела/конфликтует с ноябрьским анонсом. Текущая UI Settings page (`/settings → Usage`) показывает раздельные шкалы — это источник истины.

---

## Способ 1 — `/model opusplan` (встроенный)

Самый простой путь. Один command:

```
/model opusplan
```

Поведение:
- В **plan mode** (после `/plan` или ExitPlanMode trigger) — Opus 4.7
- В **execution mode** (нормальные edit/bash/write) — Sonnet 4.6
- Переключение автоматическое, без действий пользователя

Когда подходит:
- Линейная задача с чётким plan/exec разделением
- Не нужна параллельность
- Хочется "просто работало"

Минусы / known issues:
- **Issue #27183** (anthropics/claude-code): иногда 100% трафика идёт на Opus, Sonnet quota не расходуется — баг детекции execution mode. Workaround: явно вызывать `/plan` и `/exit-plan-mode`, не полагаться на implicit detection.
- Нет контроля над тем, КАКИЕ задачи делегируются Sonnet'у (всё или ничего).

---

## Способ 2 — Custom Sonnet subagent (рекомендуется для проекта)

Создать файл `.claude/agents/implementer.md` с явным `model: sonnet` — основная сессия (Opus) делегирует ему через Task tool.

Минимальный пример:

```markdown
---
name: implementer
description: >
  Use proactively for implementing well-specified code changes
  (bug fixes, refactors with clear scope, feature additions with design doc).
  Skip for ambiguous tasks that need architectural discussion — those stay with Opus.
model: sonnet
tools: Read, Write, Edit, Glob, Grep, Bash
permissionMode: acceptEdits
---

Ты — реализатор задач в проекте PDF Vector Framework.

# Workflow
1. Прочитай требования / план из делегирующего Opus-агента
2. Проверь существующий код (Read/Grep) — не дублируй
3. Внеси минимально достаточные правки
4. Запусти sanity-проверки (lint, syntax) если есть
5. Верни Opus краткое summary: что сделано, что не сделано, что вызывает сомнения

# Что НЕ делать
- Не меняй архитектуру / структуру модулей без явного указания
- Не добавляй новые зависимости без согласования
- Не пиши документацию (это делает Opus после ревью)

# Возврат управления
Закончи короткой выжимкой: "implemented X in [file:line], skipped Y because Z"
```

Использование:
- Opus в основной сессии планирует задачу, дробит на подзадачи
- Делегирует через Task tool: `Agent(subagent_type="implementer", prompt="...", description="...")`
- Subagent отрабатывает в своём контексте (Sonnet-квота), возвращает summary
- Opus ревьюит, инициирует следующую итерацию или фиксит мелочи

Преимущества:
- Полный контроль: явно решаешь что Opus, что Sonnet
- Output isolation — большие логи/чтение файлов не загрязняют основной Opus-контекст
- Параллельность: можно запустить N implementer'ов на независимых задачах одновременно
- В проекте уже есть прецедент opus-агента (`learning-loop.md`) — паттерн знаком

Ограничения:
- Subagent **не может породить под-subagent** (depth limit = 1)
- Subagent не наследует skills из родителя — нужно либо указать `skills:` в frontmatter, либо положить на инструкции в системный промпт
- MCP tools **недоступны** в фоновых subagent'ах (но доступны в foreground)

---

## Способ 3 — Advisor strategy (Opus читает, Sonnet делает, Opus ревьюит)

Ручной паттерн без создания subagent'а: чередуешь модели через `/model`:

```
/model opus     → Описать задачу, попросить план + риски
/model sonnet   → "Реализуй пункт 1-3 плана выше"
/model opus     → "Проверь diff на соответствие плану и edge cases"
/model sonnet   → Применить замечания
```

Когда подходит:
- Одиночная задача, нет смысла создавать постоянный subagent
- Хочешь видеть весь контекст в одной ленте
- Эксперимент с гранулярностью делегирования

Минусы:
- Мануальное переключение — забыл `/model` → потратил не ту квоту
- Контекст растёт, Sonnet получает весь объём Opus-обсуждения (дороже на input tokens)

---

## Сравнение трёх способов

| Аспект | `/model opusplan` | Custom subagent | Advisor (manual) |
|---|---|---|---|
| Setup time | 0 сек | 5 мин (написать .md) | 0 сек |
| Контроль над делегированием | низкий (auto-detect) | высокий (явный Task) | максимальный (ручной) |
| Output isolation | нет | да (subagent контекст) | нет |
| Параллельность | нет | да (N agents) | нет |
| Расход Opus context | средний | низкий (subagent в стороне) | высокий |
| Подходит для | quick tasks | recurring patterns | one-off experiments |
| Risk | Issue #27183 (100% Opus) | depth-limit | manual error |

Для проекта PDF Framework / 1C-Framework с большим объёмом repetitive impl-задач — **способ 2** наиболее sustainable. opusplan хорош для разовых задач.

---

## Cost / quota-aware рекомендации

| Что | Модель | Почему |
|---|---|---|
| Архитектурные решения, разбиение задачи, code review | Opus | Reasoning + долгий контекст |
| Bulk implementation (один файл, чёткий ТЗ) | Sonnet | Дешевле, отдельная квота |
| Mechanical refactor (rename, extract, format) | Haiku | Самое дешёвое, скорость |
| Чтение большой кодовой базы перед планом | Sonnet (через Explore) | Не тратить Opus-context |
| Тесты | Sonnet | Шаблонная работа |

Pricing (Anthropic API, для context):
- Opus 4.7: $15/M input, $75/M output
- Sonnet 4.6: $3/M input, $15/M output (5× дешевле)
- Haiku 4.5: $1/M input, $5/M output (15× дешевле Opus)

В Max-плане ты не платишь per-token, но раздельные квоты дают аналогичный экономический эффект — Sonnet-квота "почти бесплатна" пока не исчерпана.

---

## Конкретные команды для проекта

После создания `.claude/agents/implementer.md` (способ 2):

```bash
# Опус увидит agent при старте сессии
# В основной сессии (Opus):
"Делегируй реализацию [конкретная задача] на implementer subagent"
# или явно:
"Spawn implementer agent for: [task description]"
```

Чтобы проверить что agent зарегистрирован:
```
/agents
```

Чтобы видеть, на какую модель уходит запрос:
```
/usage   # current session breakdown
```

---

## Источники

- [Model configuration — Claude Code Docs](https://code.claude.com/docs/en/model-config) — `/model opusplan`, model aliases
- [Models, usage, and limits in Claude Code — Help Center](https://support.claude.com/en/articles/14552983-models-usage-and-limits-in-claude-code)
- [Using Claude Code with Pro/Max plan — Help Center](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
- [Create custom subagents — Claude Code Docs](https://code.claude.com/docs/en/sub-agents)
- [Issue #12487 — Opus and Sonnet limits independent or shared after Nov 24](https://github.com/anthropics/claude-code/issues/12487)
- [Issue #27183 — opusplan routes 100% to Opus, Sonnet quota unused](https://github.com/anthropics/claude-code/issues/27183)
- [Claude Code Advisor Strategy — MindStudio](https://www.mindstudio.ai/blog/claude-code-advisor-strategy-opus-sonnet-haiku)
- [wshobson/agents — multi-agent orchestration repo](https://github.com/wshobson/agents)
- [Pick the Right Claude Code Model — DEV Community](https://dev.to/klement_gunndu/pick-the-right-claude-code-model-for-every-task-1p6a)
- [Claude Code Limits: 4 Fixes — Product Compass](https://www.productcompass.pm/p/stop-hitting-claude-code-limits)
- [Claude Code Subagents Complete Guide — Sathish Raju, Apr 2026](https://medium.com/@sathishkraju/claude-code-subagents-the-complete-guide-to-ai-agent-delegation-d0a9aba419d0)
