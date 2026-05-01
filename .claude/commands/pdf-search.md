---
name: pdf-search
description: Search indexed PDFs and BSL/wiki/skill collections via PDF Vector & Graph Framework. Routes to the right tool by intent (search/QA/graph/visual/fallback).
allowed-tools:
  - mcp__pdf-vector-graph__search_documents
  - mcp__pdf-vector-graph__ask_question
  - mcp__pdf-vector-graph__graph_query
  - mcp__pdf-vector-graph__search_with_fallback
  - mcp__pdf-vector-graph__visual_hybrid_search
  - mcp__pdf-vector-graph__list_documents
  - mcp__pdf-vector-graph__get_stats
---

Search indexed documents (PDF, BSL, wiki, skills) using PDF Vector & Graph Framework.

User query: $ARGUMENTS

## Retrieval backbone

All collections (`pdf_documents`, `bsl_code_v4_late`, `bsl_code_v4`, `framework_code_v1`, `wiki_pages_v1`, `skill_library`, `learned_patterns`, `graph_embeddings`, `experience_embeddings`, `conversation_memory`) are indexed with **Qwen/Qwen3-Embedding-8B (4096d)** via TEI Docker (`pdf-rag-tei`). The `search_documents` tool transparently uses this backbone — you do not configure it per call. See [chapter 31](../../docs/framework%20documentation/31_QWEN3_RETRIEVAL_PRODUCTION/31.1_Обзор.md) for production retrieval details.

## Routing rules — pick exactly one tool

| Intent in user query | Tool | Notes |
|---|---|---|
| "найди / find passages / locate / mentions" | `search_documents` | default `strategy='hybrid'`, `k=5`. Other strategies: `vector`, `graph`, `bm25`, `section_first`, `graphrag_local`, `graphrag_light` |
| "ответь / what is / explain / how does" | `ask_question` | LLM-generated answer over RAG, `strategy='hybrid'` |
| "связано / related / entity / relations / какие связи" | `graph_query` | knowledge graph, `depth=1` |
| "таблица / диаграмма / chart / table / визуально" | `visual_hybrid_search` | RRF over visual + text, `k=5` |
| "может не быть в индексе / latest / recent / actuals" | `search_with_fallback` | local first, web if low confidence |
| "что проиндексировано / какие коллекции / list / stats" | `list_documents` / `get_stats` | metadata only |

**Default when ambiguous:** `search_documents` with `strategy='hybrid'`, `k=5`.

## Output format

1. One-paragraph synthesis answering the query, in the user's language.
2. Numbered citations after each fact:
   - PDF/BSL/wiki passages — `[<doc>:<page>]` или `[<file>:<line>]`
   - Graph results — `[graph:<entity>]`
3. If 0 hits — say so explicitly, suggest reformulation or `search_with_fallback`.

## Notes

- Tool `hybrid_search` does **not** exist as a separate MCP tool — `hybrid` is a `strategy` value of `search_documents`.
- Qwen3-Embedding-8B requires the TEI container to be running (`docker ps | grep pdf-rag-tei`). If retrieval returns empty results across multiple queries, check container status.
