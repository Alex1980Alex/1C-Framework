---
confidence: 0.85
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[overview]]'
- '[[triad-architecture]]'
- '[[patterns]]'
sources:
- '[.claude/skills/code-verify/SKILL.md](../../.claude/skills/code-verify/SKILL.md)'
- '[.claude/skills/learning-loop/SKILL.md](../../.claude/skills/learning-loop/SKILL.md)'
- '[14 RALPH_WIGGUM chapter](../framework documentation/14_RALPH_WIGGUM/14.1_Обзор.md)'
status: active
tags:
- automation
- verification
- pattern
- self-correction
title: Ralph Wiggum Loop
unified_id: 019e1e30-10a9-7e72-be5d-c769a631589c
updated_at: 2026-05-14 23:30:00+00:00
---

# Ralph Wiggum Loop

Итеративный self-correction паттерн: при VERIFY=FAIL фидбек ревьюера возвращается фиксер-агенту, до 3 retries. Применяется в [`code-verify`](../../.claude/skills/code-verify/SKILL.md) (knowledge-compliance / behavior-preservation / bug-fix-validation / quality-review) и в [`learning-loop`](../../.claude/skills/learning-loop/SKILL.md) (Фаза VERIFY). Имя — отсылка к идиоме «I'm helping!» (Симпсоны): простой агент, итерирующий пока не получится.

## Loop semantics

```
EXECUTE → VERIFY
            ├─ PASS → DONE
            ├─ PARTIAL → orchestrator-fix → DONE
            └─ FAIL → Ralph iteration N (max 3)
                        ├─ reference (knowledge / spec / bug description)
                        ├─ previous code attempt
                        ├─ reviewer feedback (concrete issues)
                        └─ instruction: "Fix ONLY the listed issues"
                              │
                              ▼
                        retry VERIFY
                          ├─ PASS → DONE
                          └─ N == 3 → escalate "requires manual review"
```

Каждая итерация получает **накопленный фидбек**, не начинает с нуля. После 3 неудачных циклов — объяснить root cause, не зацикливаться, пометить как `manual review`.

## Точки интеграции (11)

| # | Скилл / хук | Когда срабатывает | Mode |
|---|---|---|---|
| 1 | [`code-verify`](../../.claude/skills/code-verify/SKILL.md) | После любого Write/Edit | 4 modes — knowledge / behavior / bug-fix / quality |
| 2 | [`learning-loop`](../../.claude/skills/learning-loop/SKILL.md) | Фаза 4 VERIFY (после EXECUTE через subagent) | knowledge-compliance |
| 3 | `autoresearch` v2 | Каждая итерация Executor → Reviewer → Comparator | Comparator scoring |
| 4 | `analyze-1c-research` | Трёхагентный анализ задачи 1С | Comparator → улучшающий цикл |
| 5 | `autotestplan` / `autoreview` | MCP `auto-documenter` | Auto-generated test plans / code reviews |
| 6 | `task-evaluation` | Финальная оценка decomposition completeness | Heuristic scoring |
| 7 | `brownfield-validate` | Gap / Design / Impl validators (OpenSpec) | Cross-validator |
| 8 | `triad-factory` | Q1-Q6 design checklist для new hook/skill/MCP | Q-stage gates |
| 9 | `code-verify-reminder` hook | Stop-fallback closer (workaround #6305) | Tri-registered (PreToolUse + PostToolUse + Stop) |
| 10 | `ralph_wiggum_stop` hook | Stop event — контроль итеративного цикла | Stop |
| 11 | `ralph_activator` hook | UserPromptSubmit — активация Ralph для сложных задач | UPS |

Каноническая documentation deep — глава [14_RALPH_WIGGUM/14.1_Обзор](../framework%20documentation/14_RALPH_WIGGUM/14.1_Обзор.md).

## Принципы

1. **Bounded retries** — макс 3 итерации. Не бесконечный цикл.
2. **Concrete feedback** — ревьюер указывает строки + секции reference, не «постарайся лучше».
3. **Incremental fix** — каждая итерация фиксит ТОЛЬКО озвученные проблемы, не вводит новые изменения.
4. **One commit per iteration** — для post-mortem'ов.
5. **Escalate, don't loop** — после 3 неудач → manual review с объяснением root cause.

## Пример: knowledge-compliance loop (Learning Loop Phase 4)

```
EXECUTE (subagent): retry.py с tenacity
  └─ Source: README.md tenacity §Basic Usage

VERIFY: code-verify mode=knowledge-compliance
  reference = tenacity KB (from FETCH)
  code = retry.py
  markers = [wait_exponential_jitter, reraise=True, stop_after_attempt]
  ↓
FAIL: ревьюер: "reraise=True отсутствует — без него истинная exception скрыта"

Ralph #1:
  prompt = KB + retry.py + "Добавь reraise=True в @retry decorator"
  → fix
  → VERIFY: PASS → DONE
```

## Антипаттерны

| Плохо | Почему | Как правильно |
|---|---|---|
| Бесконечный retry-цикл | Системная проблема не решается итерациями | Макс 3 → manual review |
| Refactor «попутно» в Ralph итерации | Расширяет diff, маскирует root cause | Только targeted fix по feedback'у |
| Vague feedback («сделай лучше») | Агент не знает что чинить | Конкретные строки + ссылки на reference |
| Запуск Ralph для prose / docs | Нет verifiable reference | Только для code output (см. `code-verify`) |
| Игнорировать PARTIAL | Накопление мелких проблем | PARTIAL → orchestrator-fix, не пропускать |

## Связано

- [[patterns]] — формальный pattern catalogue (Ralph = вариант Retry With Backoff в применении к LLM verification)
- [[triad-architecture]] — hooks/skills интеграция
- Глава 18 / 20 — AutoResearch v2 трёхагентный движок использует Ralph как Comparator scoring loop
