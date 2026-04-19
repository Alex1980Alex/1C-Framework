---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.4 Fuzzy Intent Detection

**Где используется:** `.claude/hooks/shared/fuzzy_match.py`
**Как работает:** Трёхшаговое сопоставление: exact lemma → fuzzy original → fuzzy lemma. Pymorphy3 для лемматизации ("удалим" → "удалить"), rapidfuzz для опечаток. Порог 78%.
