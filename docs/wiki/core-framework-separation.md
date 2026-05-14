---
confidence: 0.3
related:
- '[[_index]]'
- '[[overview]]'
status: draft
tags:
- architecture
- structure
title: Core / Framework Separation
unified_id: 019e1e30-10a9-7781-950e-c396bbd3d66b
---

Architectural boundary between the reusable `pdf_framework` core (`src/pdf_framework/`) and project-specific application
code (`src/api/`, `src/cli/`, `src/mcp_server/`, `src/ui/`).

## Layers

- **Core** (`src/pdf_framework/`): loaders, processing, embeddings, vector_store, graph_store, search, agents, indexing
— provider pattern, async-first, no app-specific logic.

- **App** (`src/api/`, `src/cli/`, `src/mcp_server/`, `src/ui/`): consumer entrypoints.

**Status: stub.** Expand with dependency-direction rules + import-restriction examples.
