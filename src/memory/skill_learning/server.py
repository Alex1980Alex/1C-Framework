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
from typing import Any
from uuid import uuid4

from mcp import stdio_server
from mcp.server import Server
from mcp.types import TextContent, Tool

# Shared pattern-type contract (roadmap 260716 P0.1) — stdlib-only module, safe to
# import here. capture_pattern is where free-form types entered the pipeline:
# capture → confirm → detach-harvest carried them verbatim into Qdrant.
from ..vector_memory.models import PatternType, normalize_pattern_type

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


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL file, return list of dicts."""
    if not path.exists():
        return []
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return items


def _write_jsonl(path: Path, items: list[dict[str, Any]]):
    """Atomically rewrite JSONL file: tmp + os.replace, kill-safe (P0.1, roadmap 260611)."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _append_jsonl(path: Path, item: dict[str, Any]):
    """Append single dict to JSONL file."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _load_stats() -> dict[str, Any]:
    """Load learning statistics."""
    if STATS_FILE.exists():
        with open(STATS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"total_patterns": 0, "by_type": {}, "by_confidence": {"high": 0, "medium": 0, "low": 0}}


def _save_stats(stats: dict[str, Any]):
    """Save learning statistics."""
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def _derive_stats() -> dict[str, Any]:
    """Derive stats from the saved silo (source of truth) — P0.3, roadmap 260611.

    learning_stats.json остаётся write-through кэшем, не источником истины:
    инкрементный счётчик дрейфовал от фактических строк patterns.jsonl.
    """
    saved = _read_jsonl(SAVED_FILE)
    stats: dict[str, Any] = {
        "total_patterns": len(saved),
        "by_type": {},
        "by_confidence": {"high": 0, "medium": 0, "low": 0},
    }
    for pattern in saved:
        ptype = pattern.get("pattern_type", "unknown")
        stats["by_type"][ptype] = stats["by_type"].get(ptype, 0) + 1

        confidence = pattern.get("confidence", 0.5)
        if confidence >= 0.7:
            stats["by_confidence"]["high"] += 1
        elif confidence >= 0.4:
            stats["by_confidence"]["medium"] += 1
        else:
            stats["by_confidence"]["low"] += 1
    return stats


def _update_stats_on_save(pattern: dict[str, Any]):
    """Refresh the stats cache after a save (derive-on-read, cache write-through)."""
    _save_stats(_derive_stats())


# ========== §26 P1.3 write-contract helpers (content_hash + dedup + ingest) ==========
def _content_hash(content: str) -> str:
    """Fail-soft canonical content_hash. Empty string on import failure.

    Relative, not `from memory.orchestrator...` (roadmap 260716 P1.8, same class as the
    cascade): this server runs as `-m src.memory.skill_learning.server`, so the absolute
    `memory.*` namespace resolves only if something else already put <root>/src on
    sys.path — and when it does, it binds a SECOND copy of the module. The swallowed
    failure costs the write-contract itself: no hash → the record leaves the §26 dedup
    contract silently.
    """
    try:
        src = str(_PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from ..orchestrator.content_hash import hash_content

        return hash_content(content)
    except Exception:
        return ""


def _record_ingest(action: str, content_hash: str = "", **kw) -> None:
    """Fail-soft §26 ingestion-metrics emit; never breaks the MCP handler."""
    try:
        src = str(_PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from ..orchestrator.ingest_metrics import record_ingest

        record_ingest(
            "skill_learning", action, content_hash=content_hash, harvester="capture_pattern", **kw
        )
    except Exception:
        pass


def _existing_hashes() -> dict[str, tuple[str, str]]:
    """Map content_hash -> (pattern_id, silo) across pending/saved/rejected silos.

    P0.2 (roadmap 260611): rejected участвует в dedup как негативный сигнал —
    повторный capture отклонённого контента не создаёт pending. pending/saved
    идут первыми, чтобы обычный dup не маскировался под dup_rejected.
    """
    out: dict[str, tuple[str, str]] = {}
    for silo, path in (
        ("pending", PENDING_FILE),
        ("saved", SAVED_FILE),
        ("rejected", REJECTED_FILE),
    ):
        for rec in _read_jsonl(path):
            ch = rec.get("content_hash") or _content_hash(rec.get("content") or "")
            if ch and ch not in out:
                out[ch] = (rec.get("pattern_id", ""), silo)
    return out


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
                    # Enum advertises the canonical set to the caller; the handler
                    # coerces anyway (the MCP SDK does not enforce inputSchema
                    # server-side, so the schema alone is documentation, not a gate).
                    "pattern_type": {
                        "type": "string",
                        "enum": [pt.value for pt in PatternType],
                    },
                    "name": {"type": "string"},
                    "content": {"type": "string"},
                    "description": {"type": "string"},
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.7,
                    },
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


# Per-call MCP log (roadmap 260713 P2.3 / N-P2.2): второй источник истины при падении
# stdio до Post-хука. Defensive import — отсутствие helper'а не ломает сервер.
try:
    from scripts.mcp_call_log import track_call as _track_call
except Exception:  # pragma: no cover - fail-soft: log helper is optional
    from contextlib import contextmanager

    @contextmanager
    def _track_call(server: str, tool: str, **extra):  # type: ignore[misc]
        yield {"ok": True, "error_type": None}


_MCP_SERVER_SLUG = "skill-learning"


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    with _track_call(_MCP_SERVER_SLUG, name) as _st:
        # J-P0.1: контент для LLM-судьи — только при MCP_CALL_LOG_CONTENT=1.
        _st["args"] = arguments
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
                _st["ok"] = False
                _st["error_type"] = "unknown_tool"
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            _result = await handler(arguments)
            _st["result"] = _result
            return _result
        except Exception as e:
            _st["ok"] = False
            _st["error_type"] = type(e).__name__
            logger.error(f"Error in {name}: {e}", exc_info=True)
            return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_capture_pattern(args: dict) -> list[TextContent]:
    pattern_id = str(uuid4())
    now = datetime.now().isoformat()
    require_confirmation = args.get("require_confirmation", True)

    # §26 P1.3 write-contract: stamp content_hash + skip re-captures of content
    # already pending/saved (anti-flood) + emit an ingestion event.
    content_hash = _content_hash(args["content"])
    if content_hash:
        existing = _existing_hashes().get(content_hash)
        if existing is not None:
            existing_id, silo = existing
            action = "dup_rejected" if silo == "rejected" else "dup"
            if silo == "rejected":
                _record_ingest("dup", content_hash, reason="rejected")
            else:
                _record_ingest("dup", content_hash)
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "action": action,
                            "pattern_id": existing_id or pattern_id,
                            "status": action,
                            "silo": silo,
                            "name": args["name"],
                        },
                        ensure_ascii=False,
                    ),
                )
            ]

    # Coerce at the quarantine door (roadmap 260716 P0.3): junk must not reach even
    # pending, or confirm → detach-harvest would lift it into Qdrant unchanged.
    # Coerce, don't reject: capture is a fire-and-forget protocol step, so an error
    # here loses the fact — while save_pattern (explicit API, enum-documented) stays
    # strict on purpose (design Д3).
    ptype, original_ptype = normalize_pattern_type(args.get("pattern_type"))
    pattern_metadata = dict(args.get("metadata") or {})
    if original_ptype:
        pattern_metadata["original_pattern_type"] = original_ptype

    pattern = {
        "pattern_id": pattern_id,
        "pattern_type": ptype,
        "name": args["name"],
        "content": args["content"],
        "content_hash": content_hash,
        "description": args.get("description", ""),
        "confidence": args.get("confidence", 0.7),
        "tags": args.get("tags", []),
        "evidence_sources": args.get("evidence_sources", []),
        "metadata": pattern_metadata,
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

    _record_ingest("saved" if status == "saved" else "skipped", content_hash, reason=status)
    logger.info(f"Captured pattern {pattern_id}: {pattern['name']} (status={status})")
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "action": status,
                    "pattern_id": pattern_id,
                    "status": status,
                    "name": pattern["name"],
                },
                ensure_ascii=False,
            ),
        )
    ]


async def handle_batch_capture(args: dict) -> list[TextContent]:
    patterns = args.get("patterns", [])
    require_confirmation = args.get("require_confirmation", True)
    results = []
    for p in patterns:
        p["require_confirmation"] = require_confirmation
        result = await handle_capture_pattern(p)
        results.append(json.loads(result[0].text))

    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "count": len(results),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    ]


async def handle_get_pending(args: dict) -> list[TextContent]:
    limit = args.get("limit", 10)
    pending = _read_jsonl(PENDING_FILE)
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "count": len(pending),
                    "patterns": pending[:limit],
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    ]


def _detach_confirm_harvest(pattern: dict[str, Any]) -> None:
    """P3.2 (roadmap 260611): confirm → немедленный harvest в learned_patterns.

    Daemon-поток (TEI embed ~1s не должен держать MCP-ответ). Переиспользует
    ``ingest_items`` из hooks-shared ``pattern_harvest`` — детерминированный
    ``content_hash.point_id`` делает upsert идемпотентным со Stop-харвестом,
    + epoch.bump внутри → surfacing видит паттерн сразу. Загрузка модуля через
    importlib по file-path: ``src/shared`` (real package) затенил бы
    ``.claude/hooks/shared`` при обычном import ([[feedback-hook-src-shared-collision]]).
    Fail-soft: любая ошибка → лог, Stop-харвест подберёт паттерн позже.
    """

    def _run() -> None:
        try:
            import importlib.util

            ph_path = _PROJECT_ROOT / ".claude" / "hooks" / "shared" / "pattern_harvest.py"
            spec = importlib.util.spec_from_file_location("_sl_confirm_harvest", ph_path)
            if spec is None or spec.loader is None:
                return
            ph = sys.modules.get("_sl_confirm_harvest")
            if ph is None:
                ph = importlib.util.module_from_spec(spec)
                # регистрация ДО exec_module обязательна: @dataclass внутри модуля
                # резолвит sys.modules[__module__] и падает на незарегистрированном
                sys.modules["_sl_confirm_harvest"] = ph
                spec.loader.exec_module(ph)

            tags = pattern.get("tags") if isinstance(pattern.get("tags"), list) else []
            item = ph.HarvestItem(
                content=str(pattern.get("content") or ""),
                name=str(pattern.get("name") or "")[:60],
                description=str(pattern.get("description") or "")[:200],
                pattern_type=str(pattern.get("pattern_type") or "workflow-pattern"),
                source=f"skill-learning:{pattern.get('pattern_id', '')}",
                tags=[*tags, "harvested", "skill-learning"],
                confidence=0.85,
            )
            stats = ph.ingest_items([item], cap=1, harvester="confirm_pattern")
            logger.info(f"confirm-harvest: {stats}")
        except Exception as exc:
            logger.warning(f"confirm-harvest failed (Stop-harvest will retry): {exc}")

    import threading

    threading.Thread(target=_run, daemon=True).start()


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
        return [
            TextContent(
                type="text",
                text=json.dumps({"success": False, "error": "Pattern not found in pending"}),
            )
        ]

    # Save confirmed pattern
    found["updated_at"] = datetime.now().isoformat()
    _append_jsonl(SAVED_FILE, found)
    _update_stats_on_save(found)

    # Remove from pending
    _write_jsonl(PENDING_FILE, remaining)

    # P3.2: confirm = пропуск в learned_patterns — немедленный детач-harvest
    _detach_confirm_harvest(found)

    logger.info(f"Confirmed pattern {pattern_id}: {found.get('name', '')}")
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "pattern_id": pattern_id,
                    "name": found.get("name", ""),
                    "harvest": "detached",
                },
                ensure_ascii=False,
            ),
        )
    ]


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
        return [
            TextContent(
                type="text",
                text=json.dumps({"success": False, "error": "Pattern not found in pending"}),
            )
        ]

    # Save to rejected
    found["rejected_at"] = datetime.now().isoformat()
    _append_jsonl(REJECTED_FILE, found)

    # Remove from pending
    _write_jsonl(PENDING_FILE, remaining)

    logger.info(f"Rejected pattern {pattern_id}: {found.get('name', '')}")
    return [
        TextContent(
            type="text",
            text=json.dumps(
                {
                    "success": True,
                    "pattern_id": pattern_id,
                },
                ensure_ascii=False,
            ),
        )
    ]


async def handle_stats(args: dict) -> list[TextContent]:
    stats = _derive_stats()
    stats["pending_count"] = len(_read_jsonl(PENDING_FILE))
    stats["rejected_count"] = len(_read_jsonl(REJECTED_FILE))
    try:
        _save_stats({k: stats[k] for k in ("total_patterns", "by_type", "by_confidence")})
    except OSError:
        pass
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
