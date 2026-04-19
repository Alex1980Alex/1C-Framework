---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.13 Adapter

**Где используется:** `loaders/router.py`, `multitenancy/tenant_store.py`
**Ключевые классы:** `SmartLoaderRouter`, `TenantVectorStoreManager`
**Как работает:** `SmartLoaderRouter` адаптирует разные загрузчики под единый интерфейс. `TenantVectorStoreManager` изолирует данные тенантов в одном хранилище.
