---
status: active
tags: [pattern, automation]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 2.3 Config-Driven Routing

**Где используется:** `.claude/hooks/skill-router.py`
**Как работает:** Трёхуровневый роутинг: Layer A — точное совпадение фразы, Layer B — fuzzy matching (pymorphy3 + rapidfuzz), Layer C — TF-IDF семантический скоринг. Конфиг `skill-router-config.json` определяет бандлы и веса.
