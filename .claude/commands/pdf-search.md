---
name: pdf-search
description: Search indexed PDF documents using vector and graph databases
allowed-tools: mcp__pdf-vector-graph__search_documents, mcp__pdf-vector-graph__hybrid_search
---

Search PDF documents using the PDF Vector & Graph Framework.

1. Parse the user's query to determine search type (vector, graph, or hybrid)
2. Execute the appropriate search tool
3. Present results with citations (document name, page number)

User query: $ARGUMENTS
