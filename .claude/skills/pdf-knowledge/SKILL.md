---
name: pdf-knowledge
description: "PDF Vector & Graph Framework: pdf_framework, QuickRAG, граф знаний PDF. ТОЛЬКО при import pdf_framework, pdf-vector-framework, pdf search pipeline. НЕ для 1С, НЕ для Claude Code, НЕ для LangChain."
version: 1.0.0
triggers:
  - pdf search
  - vector search
  - graph query
  - document analysis
  - knowledge graph
---

# PDF Knowledge Skill

## When to Use

This skill activates when working with:
- PDF document indexing and search
- Vector similarity search
- Knowledge graph queries
- RAG (Retrieval Augmented Generation)
- Hybrid search (vector + graph)

## Available MCP Tools

When the `pdf-vector-graph` MCP server is running:

| Tool | Description |
|------|------------|
| `index_pdf` | Index a PDF into vector and graph stores |
| `search_documents` | Semantic search across indexed PDFs |
| `query_knowledge_graph` | Query entity relations in the graph |
| `hybrid_search` | Combined vector + graph search |
| `ask_documents` | RAG: ask questions about documents |

## Project Location

Code: `D:\1С-Framework`
