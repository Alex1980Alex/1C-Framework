---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b5-7d4b-8d4f-93ed181ae94f
---

# 2.4 Fuzzy Intent Detection

**Где используется:** `.claude/hooks/shared/fuzzy_match.py`
**Как работает:** Трёхшаговое сопоставление: exact lemma → fuzzy original → fuzzy lemma. Pymorphy3 для лемматизации
("удалим" → "удалить"), rapidfuzz для опечаток. Порог 78%.
