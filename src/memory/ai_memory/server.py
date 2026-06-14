"""
Memory-AI MCP Server — Important Messages System.

MCP server for managing important messages with priority and importance scoring.
Provides tools for saving, retrieving, searching, and categorizing messages.

Migrated from D:\\1C-Enterprise_Framework\\ai-memory-system\\mcp_local_scripts\\memory_server_fixed.py
Adapted: uses project-local data/memory_ai.db instead of hardcoded path.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from mcp import stdio_server
from mcp.server import Server
from mcp.types import TextContent, Tool

from .db import connect as _connect
from .db import resolve_db_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("memory-ai")

# Database path — project-local; MEMORY_AI_DB_PATH overrides (test isolation,
# same env var the orchestrator's propagation handler honors). Resolution and
# connection setup (WAL + busy_timeout, P0.4) live in .db — shared with the
# orchestrator, hooks and scripts.
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DB_PATH = resolve_db_path()

# Importance may arrive as a str label ("high") via loosely-typed callers;
# SQLite TEXT affinity would store it as-is and break float comparisons on read.
_IMPORTANCE_LABELS = {"critical": 1.0, "high": 0.9, "medium": 0.6, "normal": 0.5, "low": 0.3}


def _safe_json(raw: object, fallback_wrap: bool = False):
    """Parse a stored JSON column fail-soft (chain C2, roadmap 260612).

    Malformed legacy rows (hand-edited tags, NULL metadata) must degrade to an
    empty/wrapped value instead of blowing up every reader that scans the table.
    """
    if not raw:
        return [] if fallback_wrap else {}
    try:
        return json.loads(raw)  # type: ignore[arg-type]
    except (json.JSONDecodeError, TypeError):
        return [str(raw)] if fallback_wrap else {}


def _coerce_importance(value: object, default: float = 0.7) -> float:
    """Coerce an importance value to float clamped to [0, 1]."""
    if isinstance(value, str):
        value = _IMPORTANCE_LABELS.get(value.strip().lower(), value)
    try:
        return max(0.0, min(1.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def ensure_db():
    """Ensure database and tables exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS important_messages (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                category TEXT DEFAULT 'general',
                tags TEXT,
                created_at TEXT,
                updated_at TEXT,
                metadata TEXT
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_importance ON important_messages(importance DESC)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON important_messages(category)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_created ON important_messages(created_at DESC)"
        )
        conn.commit()
    logger.info(f"Database initialized: {DB_PATH}")


ensure_db()

app = Server("memory-ai")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_important_messages",
            description="Retrieve important messages from memory. Filter by importance threshold or category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of messages to return",
                        "default": 10,
                    },
                    "min_importance": {
                        "type": "number",
                        "description": "Minimum importance score (0.0-1.0)",
                        "default": 0.5,
                    },
                    "category": {"type": "string", "description": "Filter by category (optional)"},
                },
            },
        ),
        Tool(
            name="save_important_message",
            description="Save an important message to memory with importance score and category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The message content to save"},
                    "importance": {
                        "type": "number",
                        "description": "Importance score (0.0-1.0)",
                        "default": 0.7,
                    },
                    "category": {
                        "type": "string",
                        "description": "Category for the message",
                        "default": "general",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for the message",
                    },
                },
                "required": ["content"],
            },
        ),
        Tool(
            name="search_messages",
            description="Search important messages by content or tags.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Maximum results", "default": 10},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="delete_message",
            description="Delete a message by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "ID of the message to delete"},
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="get_categories",
            description="Get list of all categories with message counts and average importance.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        handlers = {
            "get_important_messages": get_important_messages,
            "save_important_message": save_important_message,
            "search_messages": search_messages,
            "delete_message": delete_message,
            "get_categories": get_categories,
        }
        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        return await handler(arguments)
    except Exception as e:
        logger.error(f"Error in {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_important_messages(args: dict) -> list[TextContent]:
    limit = args.get("limit", 10)
    min_importance = args.get("min_importance", 0.5)
    category = args.get("category")

    with _connect(DB_PATH) as conn:
        cursor = conn.cursor()

        if category:
            cursor.execute(
                "SELECT id, content, importance, category, tags, created_at, metadata "
                "FROM important_messages WHERE importance >= ? AND category = ? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (min_importance, category, limit),
            )
        else:
            cursor.execute(
                "SELECT id, content, importance, category, tags, created_at, metadata "
                "FROM important_messages WHERE importance >= ? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (min_importance, limit),
            )

        rows = cursor.fetchall()

    messages = []
    for row in rows:
        messages.append(
            {
                "id": row[0],
                "content": row[1],
                "importance": row[2],
                "category": row[3],
                "tags": _safe_json(row[4], fallback_wrap=True),
                "created_at": row[5],
                "metadata": _safe_json(row[6]),
            }
        )

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {"count": len(messages), "messages": messages}, ensure_ascii=False, indent=2
            ),
        )
    ]


def _content_hash(content: str) -> str:
    """Fail-soft canonical content_hash (§26 P1.3). Empty string on import failure."""
    try:
        src = str(_PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.orchestrator.content_hash import hash_content

        return hash_content(content)
    except Exception:
        return ""


def _record_ingest(
    action: str, content_hash: str = "", harvester: str = "save_important_message", **kw
) -> None:
    """Fail-soft §26 ingestion-metrics emit; never breaks the MCP handler."""
    try:
        src = str(_PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.orchestrator.ingest_metrics import record_ingest

        record_ingest("memory_ai", action, content_hash=content_hash, harvester=harvester, **kw)
    except Exception:
        pass


async def save_important_message(args: dict) -> list[TextContent]:
    content = args.get("content")
    if not content:
        return [TextContent(type="text", text="Error: content is required")]

    importance = _coerce_importance(args.get("importance", 0.7))
    category = args.get("category", "general")
    tags = args.get("tags", [])

    # §26 P1.3 write-contract: stamp content_hash, dedup on identical content (no
    # second row for a re-save), and emit an ingestion event for observability.
    content_hash = _content_hash(content)
    msg_id = str(uuid4())
    now = datetime.now().isoformat()

    with _connect(DB_PATH) as conn:
        cursor = conn.cursor()
        existing = cursor.execute(
            "SELECT id FROM important_messages WHERE content = ? LIMIT 1", (content,)
        ).fetchone()
        if existing:
            _record_ingest("dup", content_hash)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"success": True, "action": "dup", "id": existing[0]}, ensure_ascii=False
                    ),
                )
            ]
        cursor.execute(
            "INSERT INTO important_messages (id, content, importance, category, tags, created_at, updated_at, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                msg_id,
                content,
                importance,
                category,
                json.dumps(tags),
                now,
                now,
                json.dumps({"content_hash": content_hash}),
            ),
        )
        conn.commit()

    _record_ingest("saved", content_hash)
    logger.info(f"Saved message {msg_id} with importance {importance}")
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "action": "saved",
                    "id": msg_id,
                    "importance": importance,
                    "category": category,
                },
                ensure_ascii=False,
            ),
        )
    ]


def _tokenize(text: str) -> set[str]:
    """casefold + RU-stem tokens (P2.G2); empty set if text_norm unavailable."""
    try:
        from ..text_norm import tokenize

        return tokenize(text)
    except Exception:
        return set()


async def search_messages(args: dict) -> list[TextContent]:
    query = args.get("query", "")
    limit = args.get("limit", 10)

    # P2.G2 (roadmap 260612): bare ``LIKE %q%`` missed Cyrillic morphoforms
    # (SQLite LOWER is ASCII-only). Scan an importance/recency-ordered window and
    # rank by stemmed token overlap; fall back to legacy LIKE when the query
    # yields no tokens (emoji/CJK) or text_norm is unavailable.
    tokens = _tokenize(query)
    with _connect(DB_PATH) as conn:
        cursor = conn.cursor()
        if tokens:
            cursor.execute(
                "SELECT id, content, importance, category, tags, created_at "
                "FROM important_messages "
                "ORDER BY importance DESC, created_at DESC LIMIT 2000"
            )
            scored = []
            for row in cursor.fetchall():
                row_tokens = _tokenize(f"{row[1] or ''} {row[4] or ''}")
                matched = len(tokens & row_tokens)
                if matched:
                    scored.append((matched / len(tokens), row))
            scored.sort(key=lambda x: x[0], reverse=True)
            rows = [row for _score, row in scored[:limit]]
        else:
            cursor.execute(
                "SELECT id, content, importance, category, tags, created_at "
                "FROM important_messages WHERE content LIKE ? OR tags LIKE ? "
                "ORDER BY importance DESC, created_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            )
            rows = cursor.fetchall()

    messages = []
    for row in rows:
        messages.append(
            {
                "id": row[0],
                "content": row[1],
                "importance": row[2],
                "category": row[3],
                "tags": _safe_json(row[4], fallback_wrap=True),
                "created_at": row[5],
            }
        )

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {"query": query, "count": len(messages), "messages": messages},
                ensure_ascii=False,
                indent=2,
            ),
        )
    ]


def _cleanup_links(msg_id: str) -> int:
    """P2.G5 (roadmap 260612): drop link_registry edges referencing a deleted row.

    Direct SQL on the registry DB — importing LinkRegistry would pull the heavy
    orchestrator package into this server. Fail-soft: a locked/absent registry
    must not break the delete itself.
    """
    try:
        import os
        import sqlite3

        lr_path = Path(
            os.environ.get("LINK_REGISTRY_PATH") or _PROJECT_ROOT / "data" / "link_registry.db"
        )
        if not lr_path.exists():
            return 0
        uid = f"episodic:memory-ai:{msg_id}"
        conn = sqlite3.connect(str(lr_path), timeout=2)
        try:
            cur = conn.execute(
                "DELETE FROM entity_links WHERE source_id = ? OR target_id = ?", (uid, uid)
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()
    except Exception:
        return 0


async def delete_message(args: dict) -> list[TextContent]:
    msg_id = args.get("message_id")
    if not msg_id:
        return [TextContent(type="text", text="Error: message_id is required")]

    with _connect(DB_PATH) as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT metadata FROM important_messages WHERE id = ?", (msg_id,)
        ).fetchone()
        cursor.execute("DELETE FROM important_messages WHERE id = ?", (msg_id,))
        deleted = cursor.rowcount
        conn.commit()

    links_removed = 0
    if deleted:
        links_removed = _cleanup_links(msg_id)
        # W6 observability (roadmap 260612 P4): deletes were invisible to fact-trace.
        try:
            content_hash = (json.loads(row[0]) or {}).get("content_hash", "") if row else ""
        except (json.JSONDecodeError, TypeError):
            content_hash = ""
        _record_ingest("deleted", content_hash, harvester="delete_message")

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {"success": deleted > 0, "deleted": deleted, "links_removed": links_removed}
            ),
        )
    ]


async def get_categories(args: dict) -> list[TextContent]:
    with _connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT category, COUNT(*) as count, AVG(importance) as avg_importance "
            "FROM important_messages GROUP BY category ORDER BY count DESC"
        )
        rows = cursor.fetchall()

    categories = [
        {"category": row[0], "count": row[1], "avg_importance": round(row[2], 2)} for row in rows
    ]
    return [
        TextContent(
            type="text", text=json.dumps({"categories": categories}, ensure_ascii=False, indent=2)
        )
    ]


async def main():
    logger.info("Starting Memory-AI MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
