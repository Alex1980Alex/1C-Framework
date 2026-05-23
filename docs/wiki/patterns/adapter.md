---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b1-74cf-9610-db24d0f36df3
---

# 1.13 Adapter

**Где используется:** `loaders/router.py`, `multitenancy/tenant_store.py`
**Ключевые классы:** `SmartLoaderRouter`, `TenantVectorStoreManager`
**Как работает:** `SmartLoaderRouter` адаптирует разные загрузчики под единый интерфейс. `TenantVectorStoreManager`
изолирует данные тенантов в одном хранилище.
