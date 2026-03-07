"""
Skill Learning MCP Server — Pattern Capture and Confirmation.

MCP server for capturing patterns from tool usage, reviewing pending
patterns, and saving confirmed patterns to Vector Memory.

Migrated from D:\\1C-Enterprise_Framework\\skill-learning-mcp\\server.py
Adapted: uses project-local data/skill_learning/ for storage.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from mcp.server import Server
from mcp import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("skill-learning")

# Storage paths — project-local
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
STORAGE_DIR = _PROJECT_ROOT / "data" / "skill_learning"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

PENDING_FILE = STORAGE_DIR / "pending_patterns.jsonl"
SAVED_FILE = STORAGE_DIR / "patterns.jsonl"
REJECTED_FILE = STORAGE_DIR / "rejected_patterns.jsonl"
STATS_FILE = STORAGE_DIR / "learning_stats.json"


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read JSONL file, return list of dicts."""
    if not path.exists():
        return []
    items = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def _write_jsonl(path: Path, items: List[Dict[str, Any]]):
    """Write list of dicts to JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _append_jsonl(path: Path, item: Dict[str, Any]):
    """Append single dict to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _load_stats() -> Dict[str, Any]:
    """Load learning statistics."""
    if STATS_FILE.exists():
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"total_patterns": 0, "by_type": {}, "by_confidence": {"high": 0, "medium": 0, "low": 0}}


def _save_stats(stats: Dict[str, Any]):
    """Save learning statistics."""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def _update_stats_on_save(pattern: Dict[str, Any]):
    """Update stats when a pattern is saved."""
    stats = _load_stats()
    stats["total_patterns"] = stats.get("total_patterns", 0) + 1

    ptype = pattern.get("pattern_type", "unknown")
    stats.setdefault("by_type", {})
    stats["by_type"][ptype] = stats["by_type"].get(ptype, 0) + 1

    confidence = pattern.get("confidence", 0.5)
    stats.setdefault("by_confidence", {"high": 0, "medium": 0, "low": 0})
    if confidence >= 0.7:
        stats["by_confidence"]["high"] += 1
    elif confidence >= 0.4:
        stats["by_confidence"]["medium"] += 1
    else:
        stats["by_confidence"]["low"] += 1

    _save_stats(stats)


# ========== MCP Server ==========

app = Server("skill-learning")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="capture_pattern",
            description="Capture a pattern from tool use. Saves as pending for user confirmation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern_type": {"type": "string"},
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                    "description": {"type": "string"},
                    "confidence": {"type": "number", "default": 0.7},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "evidence_sources": {"type": "array", "items": {"type": "object"}},
                    "metadata": {"type": "object"},
                    "require_confirmation": {"type": "boolean", "default": True},
                },
                "required": ["pattern_type", "name", "content"],
            },
        ),
        Tool(
            name="batch_capture",
            description="Capture multiple patterns at once.",
            inputSchema={
                "type": "object",
                "properties": {
                    "patterns": {"type": "array", "items": {"type": "object"}},
                    "require_confirmation": {"type": "boolean", "default": True},
                },
                "required": ["patterns"],
            },
        ),
        Tool(
            name="get_pending_patterns",
            description="Get patterns waiting for user confirmation.",
            inputSchema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 10}},
            },
        ),
        Tool(
            name="confirm_pattern",
            description="Confirm and save a pending pattern to persistent storage.",
            inputSchema={
                "type": "object",
                "properties": {"pattern_id": {"type": "string"}},
                "required": ["pattern_id"],
            },
        ),
        Tool(
            name="reject_pattern",
            description="Reject a pending pattern.",
            inputSchema={
                "type": "object",
                "properties": {"pattern_id": {"type": "string"}},
                "required": ["pattern_id"],
            },
        ),
        Tool(
            name="get_learning_stats",
            description="Get learning statistics: total patterns, by type, by confidence.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="health_check",
            description="Check storage health and pending count.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        handlers = {
            "capture_pattern": handle_capture_pattern,
            "batch_capture": handle_batch_capture,
            "get_pending_patterns": handle_get_pending,
            "confirm_pattern": handle_confirm,
            "reject_pattern": handle_reject,
            "get_learning_stats": handle_stats,
            "health_check": handle_health,
        }
        handler = handlers.get(name)
        if not handler:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
        return await handler(arguments)
    except Exception as e:
        logger.error(f"Error in {name}: {e}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_capture_pattern(args: dict) -> list[TextContent]:
    pattern_id = str(uuid4())
    now = datetime.now().isoformat()
    require_confirmation = args.get("require_confirmation", True)

    pattern = {
        "pattern_id": pattern_id,
        "pattern_type": args["pattern_type"],
        "name": args["name"],
        "content": args["content"],
        "description": args.get("description", ""),
        "confidence": args.get("confidence", 0.7),
        "tags": args.get("tags", []),
        "evidence_sources": args.get("evidence_sources", []),
        "metadata": args.get("metadata", {}),
        "application_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "created_at": now,
        "updated_at": now,
        "version": 1,
        "archived": False,
    }

    if require_confirmation:
        _append_jsonl(PENDING_FILE, pattern)
        status = "pending"
    else:
        _append_jsonl(SAVED_FILE, pattern)
        _update_stats_on_save(pattern)
        status = "saved"

    logger.info(f"Captured pattern {pattern_id}: {pattern['name']} (status={status})")
    return [TextContent(type="text", text=json.dumps({
        "success": True, "pattern_id": pattern_id, "status": status, "name": pattern["name"],
    }, ensure_ascii=False))]


async def handle_batch_capture(args: dict) -> list[TextContent]:
    patterns = args.get("patterns", [])
    require_confirmation = args.get("require_confirmation", True)
    results = []
    for p in patterns:
        p["require_confirmation"] = require_confirmation
        result = await handle_capture_pattern(p)
        results.append(json.loads(result[0].text))

    return [TextContent(type="text", text=json.dumps({
        "success": True, "count": len(results), "results": results,
    }, ensure_ascii=False, indent=2))]


async def handle_get_pending(args: dict) -> list[TextContent]:
    limit = args.get("limit", 10)
    pending = _read_jsonl(PENDING_FILE)
    return [TextContent(type="text", text=json.dumps({
        "count": len(pending), "patterns": pending[:limit],
    }, ensure_ascii=False, indent=2))]


async def handle_confirm(args: dict) -> list[TextContent]:
    pattern_id = args["pattern_id"]
    pending = _read_jsonl(PENDING_FILE)

    found = None
    remaining = []
    for p in pending:
        if p.get("pattern_id") == pattern_id:
            found = p
        else:
            remaining.append(p)

    if not found:
        return [TextContent(type="text", text=json.dumps({"success": False, "error": "Pattern not found in pending"}))]

    # Save confirmed pattern
    found["updated_at"] = datetime.now().isoformat()
    _append_jsonl(SAVED_FILE, found)
    _update_stats_on_save(found)

    # Remove from pending
    _write_jsonl(PENDING_FILE, remaining)

    logger.info(f"Confirmed pattern {pattern_id}: {found.get('name', '')}")
    return [TextContent(type="text", text=json.dumps({
        "success": True, "pattern_id": pattern_id, "name": found.get("name", ""),
    }, ensure_ascii=False))]


async def handle_reject(args: dict) -> list[TextContent]:
    pattern_id = args["pattern_id"]
    pending = _read_jsonl(PENDING_FILE)

    found = None
    remaining = []
    for p in pending:
        if p.get("pattern_id") == pattern_id:
            found = p
        else:
            remaining.append(p)

    if not found:
        return [TextContent(type="text", text=json.dumps({"success": False, "error": "Pattern not found in pending"}))]

    # Save to rejected
    found["rejected_at"] = datetime.now().isoformat()
    _append_jsonl(REJECTED_FILE, found)

    # Remove from pending
    _write_jsonl(PENDING_FILE, remaining)

    logger.info(f"Rejected pattern {pattern_id}: {found.get('name', '')}")
    return [TextContent(type="text", text=json.dumps({
        "success": True, "pattern_id": pattern_id,
    }, ensure_ascii=False))]


async def handle_stats(args: dict) -> list[TextContent]:
    stats = _load_stats()
    pending_count = len(_read_jsonl(PENDING_FILE))
    stats["pending_count"] = pending_count
    return [TextContent(type="text", text=json.dumps(stats, ensure_ascii=False, indent=2))]


async def handle_health(args: dict) -> list[TextContent]:
    health = {
        "storage_dir": str(STORAGE_DIR),
        "storage_exists": STORAGE_DIR.exists(),
        "pending_count": len(_read_jsonl(PENDING_FILE)),
        "saved_count": len(_read_jsonl(SAVED_FILE)),
        "rejected_count": len(_read_jsonl(REJECTED_FILE)),
    }
    return [TextContent(type="text", text=json.dumps(health, indent=2))]


async def main():
    logger.info("Starting Skill-Learning MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
