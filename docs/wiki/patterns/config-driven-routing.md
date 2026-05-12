---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- automation
unified_id: 019e1e2c-a8b3-7493-b957-f6b212c45061
---

# 2.3 Config-Driven Routing

**Где используется:** `.claude/hooks/skill-router.py`
**Как работает:** Трёхуровневый роутинг: Layer A — точное совпадение фразы, Layer B — fuzzy matching (pymorphy3 + rapidfuzz), Layer C — TF-IDF семантический скоринг. Конфиг `skill-router-config.json` определяет бандлы и веса.
