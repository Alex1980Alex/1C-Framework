---
confidence: 0.8095620357813729
content_hash: e62eae7fbd13cbb9
content_type: wiki
created_at: '2026-07-05T04:22:37.392906'
importance: 0.5
memory_type: wiki
source: obsidian-vault
tags:
- 1c
- coder
- feedback
- opus
- planner
- zai
title: Opus = Planner/Reviewer, Z.AI = Coder
unified_id: wiki:obsidian-vault:8d563043-9aa3-4cbe-a9ed-b167dbf2d26b
updated_at: '2026-07-05T04:22:37.392909'
version: 1
status: draft

---

## Content

Opus = Planner/Reviewer, Z.AI = Coder | Opus must delegate ALL programming tasks to Z.AI, focus only on planning, control, and code review | Opus = планировщик + контроллер + ревьюер. Z.AI GLM-5.1 = исполнитель кода (Python, JS, TS и др.).
**ИСКЛЮЧЕНИЕ: BSL/1С код пишет ТОЛЬКО Opus** — Z.AI не знает платформу 1С.

**Why:** Пользователь хочет максимально использовать Z.AI для программирования, Opus-токены — только на интеллектуальную работу. Но BSL/1С — специфический язык, Z.AI галлюцинирует API 1С.

**How to apply:**
1. Python/JS/TS код → декомпозиция → промпт для Z.AI → `llm_complete()` → ревью → Write
2. BSL/1С код (.bsl) → Opus пишет сам (Never delegate)
3. Opus пишет сам ТАКЖЕ: архитектуру, отладку, security-критичный код
4. Фазы реализации (phases) Python = Z.AI с ревью Opus
5. Фазы реализации 1С = только Opus
6. Формат промпта для Z.AI: задача + контекст (существующий код) + ограничения + формат вывода
