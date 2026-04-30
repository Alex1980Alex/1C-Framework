# framework-search-mcp

MCP server exposing the `framework_code_v1` Qdrant collection for semantic
search over the framework's own codebase.

## Tools

| Name | Purpose |
|------|---------|
| `search_code(query, k, language?, path_glob?)` | Semantic search by description |
| `find_similar(file_path, k)` | Similar code by file content |
| `index_status()` | Collection stats + sample distributions |
| `reindex_changed()` | Manually trigger incremental reindex |

## Lazy mtime check

Before every `search_code`, the server scans for files whose on-disk `mtime`
exceeds the `mtime` recorded in their Qdrant payload. Stale files (and brand-new
files) are reindexed on the fly, capped at 50 files per pass and throttled to
once per 30 seconds. This is a safety net for cold starts and watcher downtime
(Stage 3).

## Run

```bash
# stdio MCP (the way Claude Code launches it)
python tools/framework-search-mcp/server.py

# Custom Qdrant/TEI URLs
python tools/framework-search-mcp/server.py \
    --qdrant-url http://localhost:6333 \
    --tei-url http://localhost:8080 \
    --collection framework_code_v1
```

## Register in `.mcp.json`

```json
{
  "mcpServers": {
    "framework-search": {
      "command": "C:/1С-Framework/.venv/Scripts/python.exe",
      "args": ["tools/framework-search-mcp/server.py"]
    }
  }
}
```

## Dependencies

- `mcp` (FastMCP) — already in repo via other MCP servers
- `qdrant-client` ≥ 1.13
- `httpx`, `tenacity` — already used by `src/framework_search/embedder.py`
- TEI Docker (`pdf-rag-tei`) running on port 8080
- Qdrant running on port 6333

## Related

- Pipeline: [src/framework_search/](../../src/framework_search/)
- CLI: [scripts/index_framework.py](../../scripts/index_framework.py)
- Skill: [.claude/skills/framework-search/SKILL.md](../../.claude/skills/framework-search/SKILL.md)
- Roadmap: docs/roadmap/260426_ROADMAP_PHASE_8_QWEN3_EMBEDDING_REINDEX.md §25
