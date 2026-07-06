---
confidence: 0.8055161139183816
content_hash: 701ae55346e97159
content_type: wiki
created_at: '2026-07-07T00:03:22.485928'
importance: 0.5
memory_type: wiki
source: obsidian-vault
status: draft
tags:
- agents
- feedback
- for
- hooks
- use
- zai
title: Agent model selection and delegation rules
unified_id: wiki:obsidian-vault:7d91fe17-91a9-40e0-840f-04fc39d3f0b7
updated_at: '2026-07-07T00:03:22.485930'
version: 1
---

## Content

Agent model selection and delegation rules | Decision matrix for Agent() model selection, when to use Agent vs direct tools, and Z.AI delegation for subagents | ## Правило 1: Decision matrix для Agent() model

| Тип задачи агента | Модель | Обоснование |
|---|---|---|
| WebSearch/WebFetch research | **НЕ ИСПОЛЬЗОВАТЬ Agent** | Прямые WebSearch параллельно быстрее и бесплатнее |
| Поиск по кодовой базе (Glob/Grep/Read) | **НЕ ИСПОЛЬЗОВАТЬ Agent** | Прямые Glob/Grep быстрее |
| Глубокий анализ кода (10+ файлов) | `model: "sonnet"` | Sonnet достаточен для code analysis |
| Код-генерация в изолированном worktree | `model: "sonnet"` | Sonnet пишет код, Opus ревьюит |
| Архитектурный анализ (cross-cutting) | `model: "sonnet"` или без Agent | Opus в main conversation лучше |
| Простой lookup / file search | `model: "haiku"` | Минимальная задача |

**Why:** 7 Agent() на Opus = ~350K tokens (~$25). Те же 7 WebSearch = ~0 tokens Opus. Agent на haiku = ~$0.50.

**How to apply:**
1. ПЕРЕД вызовом Agent() → спроси: "Могу ли я решить это прямым WebSearch/Glob/Read?"
2. Если да → НЕ используй Agent, используй прямые tools
3. Если нужен Agent → ВСЕГДА указывай `model: "haiku"` или `model: "sonnet"`
4. `model: "opus"` для Agent → НИКОГДА (Opus = main conversation only)

## Правило 2: Agent vs Direct Tools

```
Задача → Можно решить 1-6 прямыми tools? → ДА → Прямые tools (WebSearch, Glob, Read)
                                            → НЕТ → Нужен Agent?
                                                     → Research/поиск → model: "haiku"
                                                     → Анализ/код → model: "sonnet"
                         
