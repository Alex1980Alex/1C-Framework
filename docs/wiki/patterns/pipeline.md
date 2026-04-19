---
status: active
tags: [pattern, architecture]
related: ["[[PATTERNS]]"]
created: 2026-04-20
---

# 1.10 Pipeline

**Где используется:** `processing/pipeline.py`, `search/pipelines/`
**Ключевые классы:** `ProcessingPipeline`, `TwoStagePipeline`, `SectionFirstPipeline`
**Как работает:** Конвейер последовательно пропускает данные через этапы: split → page_assign → dedup → enrich. Каждый этап — независимый трансформер.
