---
confidence: 0.5
created: 2026-04-20
related:
- '[[PATTERNS]]'
status: active
tags:
- pattern
- architecture
unified_id: 019e1e2c-a8b7-719f-91ca-3e5a2d48e6c6
---

# 1.10 Pipeline

**Где используется:** `processing/pipeline.py`, `search/pipelines/`
**Ключевые классы:** `ProcessingPipeline`, `TwoStagePipeline`, `SectionFirstPipeline`
**Как работает:** Конвейер последовательно пропускает данные через этапы: split → page_assign → dedup → enrich. Каждый
этап — независимый трансформер.
