"""§26 P1 D1.1 — patterns-harvester core (Qdrant/TEI fail-soft).

Mines two high-signal sources into the ``learned_patterns`` Qdrant collection:

  1. **Confirmed feedback-drafts** — ``data/memory_drafts/*.md`` whose frontmatter
     ``metadata.status`` was flipped to ``confirmed``/``approved`` by a human and
     whose rule placeholders are filled. (Pending/placeholder drafts are skipped —
     the curated ``MEMORY.md`` layer stays manual per §26 §6; this only feeds the
     semantic pattern store, which is gated, not the curated ``.md``.)
  2. **Session-lessons** — bullet lines under the "Lessons" section of the §23
     lifecycle cache (``data/lifecycle/*.md``), with an auto-task-title noise
     filter so the docs-tracker / code-verify chatter never floods patterns.

Harvested payloads MIRROR ``vector_memory.server._pattern_to_payload`` (+
``content_hash``) so they are indistinguishable from manually saved patterns to
§24 surfacing and §22 confidence. ``save_pattern`` itself is MCP-only, so we
upsert directly.

Gating (anti-flood, §26 §6):
  - dedup via deterministic ``UUID5(content_hash)`` point id → re-harvest = 0 new
    (cheap ``retrieve`` check, no embedding spent on dups);
  - per-run cap (``cap``, default 5);
  - content-quality floor (placeholder / noise / min-length);
  - confidence seeded at Beta(7,3) prior = 0.70 (matches ``save_pattern``).

Fail-soft: Qdrant/TEI unavailable → stats carry an ``errors`` count, never raises.
Reversible: the Stop-hook honours ``PATTERNS_HARVEST_DISABLE=1``.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DRAFTS_DIR = PROJECT_ROOT / "data" / "memory_drafts"
LIFECYCLE_DIR = PROJECT_ROOT / "data" / "lifecycle"
# §26 P2 D2.2: skill-learning silo — confirmed patterns live in patterns.jsonl
# (pending_patterns.jsonl is awaiting review; confirm = move into this file).
SKILL_LEARNING_FILE = PROJECT_ROOT / "data" / "skill_learning" / "patterns.jsonl"

COLLECTION = os.environ.get("LEARNING_COLLECTION_NAME", "learned_patterns")
QDRANT_HOST = os.environ.get("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
# Passage-side TEI embed: NO query instruction prefix (stored docs live in
# passage space; the query prefix belongs only to search-time embeddings).
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080") + "/embed"

# Fixed namespace so the same content always maps to the same point id.
_NS = uuid.UUID("a1b2c3d4-1111-2222-3333-444455556666")

DEFAULT_CAP = 5
MIN_CONTENT_LEN = 25

# Auto-generated task-title chatter that ends up in lifecycle "Lessons" but is
# NOT a real lesson — must never become a pattern.
_LESSON_NOISE_RE = re.compile(
    r"^(?:\*\*)?(?:обнови|обновить доки|запустить code-verify|run code-verify|"
    r"update docs|done:|completed tasks|выполнен|—|-)\b",
    re.IGNORECASE,
)
# Unfilled draft placeholders → draft is not actually confirmed yet.
_PLACEHOLDER_RE = re.compile(r"<[^>\n]{2,40}>")

# --- content_hash + point_id: reuse canonical helpers, inline fallback (fail-soft) ---
_shared_point_id = None
try:  # pragma: no cover - import path depends on layout
    import sys

    if str(PROJECT_ROOT / "src") not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from memory.orchestrator.content_hash import hash_content as _hash_content
    from memory.orchestrator.content_hash import point_id as _shared_point_id
except Exception:  # pragma: no cover
    import hashlib

    def _hash_content(text: str) -> str:
        return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()[:16]


try:  # pragma: no cover
    from memory.vector_memory.confidence import derive_confidence as _derive_conf
except Exception:  # pragma: no cover

    def _derive_conf(succ: float, fail: float) -> float:
        return (7.0 + succ) / (10.0 + succ + fail)


@dataclass
class HarvestItem:
    content: str
    name: str
    description: str
    pattern_type: str
    source: str
    tags: list[str] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        return _hash_content(self.content)


def _point_id(content_hash: str) -> str:
    return str(uuid.uuid5(_NS, content_hash))


def _passage_embed(text: str, timeout: float = 3.0) -> list[float] | None:
    """Embed text as a passage via TEI /embed (no query instruction). None on error."""
    try:
        payload = json.dumps(
            {
                "inputs": [text[:8000]],
                "normalize": True,
                "truncate": True,
                "truncation_direction": "Right",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            TEI_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, list) and data and isinstance(data[0], list):
            return data[0]
        if isinstance(data, dict) and isinstance(data.get("embeddings"), list):
            vecs = data["embeddings"]
            if vecs and isinstance(vecs[0], list):
                return vecs[0]
    except Exception:
        return None
    return None


def _split_frontmatter(md: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if no/invalid frontmatter."""
    if not md.startswith("---"):
        return {}, md
    parts = md.split("---", 2)
    if len(parts) < 3:
        return {}, md
    try:
        import yaml

        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}
    return (meta if isinstance(meta, dict) else {}), parts[2].strip()


def _field(body: str, label: str) -> str:
    """Extract '**Label:** value' (single line) from a draft body."""
    m = re.search(rf"\*\*{re.escape(label)}[^:]*:\*\*\s*(.+)", body)
    return m.group(1).strip() if m else ""


def iter_confirmed_drafts(drafts_dir: Path = DRAFTS_DIR) -> list[HarvestItem]:
    """Confirmed, placeholder-free feedback-drafts → HarvestItems."""
    items: list[HarvestItem] = []
    if not drafts_dir.exists():
        return items
    for path in sorted(drafts_dir.glob("*.md")):
        try:
            md = path.read_text(encoding="utf-8")
        except Exception:
            continue
        meta, body = _split_frontmatter(md)
        status = str(
            ((meta.get("metadata") or {}) if isinstance(meta, dict) else {}).get("status", "")
        ).lower()
        if status not in ("confirmed", "approved"):
            continue
        rule = _field(body, "Правило") or _field(body, "Rule")
        why = _field(body, "Why") or _field(body, "Причина")
        how = _field(body, "How to apply") or _field(body, "How")
        # quality floor: real rule text, no unfilled placeholders
        if len(rule) < MIN_CONTENT_LEN or _PLACEHOLDER_RE.search(rule):
            continue
        parts = [f"Правило: {rule}"]
        if why:
            parts.append(f"Why: {why}")
        if how:
            parts.append(f"How: {how}")
        content = "\n".join(parts)
        desc = str(meta.get("description") or "").strip()
        if not desc or _PLACEHOLDER_RE.search(desc):
            desc = rule[:120]
        items.append(
            HarvestItem(
                content=content,
                name=rule[:60],
                description=desc,
                pattern_type="code-convention",
                source=f"feedback-draft:{path.name}",
                tags=["feedback", "harvested"],
            )
        )
    return items


def _lesson_lines(body: str) -> list[str]:
    """Bullet lines under a 'Lessons' section, noise-filtered."""
    out: list[str] = []
    in_section = False
    for line in body.splitlines():
        h = line.strip()
        if h.startswith("## "):
            in_section = "lesson" in h.lower() or "урок" in h.lower()
            continue
        if not in_section:
            continue
        if not h.startswith(("- ", "* ")):
            continue
        text = h[2:].strip()
        if len(text) < MIN_CONTENT_LEN or _LESSON_NOISE_RE.match(text):
            continue
        out.append(text)
    return out


def iter_session_lessons(
    lifecycle_dir: Path = LIFECYCLE_DIR,
    max_age_hours: int = 48,
    now: datetime | None = None,
) -> list[HarvestItem]:
    """Genuine lesson bullets from recent lifecycle caches → HarvestItems."""
    items: list[HarvestItem] = []
    if not lifecycle_dir.exists():
        return items
    now = now or datetime.now()
    cutoff = now - timedelta(hours=max_age_hours)
    for path in sorted(lifecycle_dir.glob("*.md")):
        try:
            if max_age_hours and datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                continue
            body = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for text in _lesson_lines(body):
            items.append(
                HarvestItem(
                    content=text,
                    name=text[:60],
                    description=text[:120],
                    pattern_type="workflow-pattern",
                    source=f"session-lesson:{path.name}",
                    tags=["lesson", "harvested"],
                )
            )
    return items


def iter_confirmed_skill_patterns(jsonl_file: Path = SKILL_LEARNING_FILE) -> list[HarvestItem]:
    """§26 P2 D2.2: confirmed (non-archived) skill-learning patterns → HarvestItems.

    A record in patterns.jsonl IS confirmed (capture→pending→confirm moves it here);
    archived records and too-short content are skipped.
    """
    items: list[HarvestItem] = []
    if not jsonl_file.exists():
        return items
    try:
        lines = jsonl_file.read_text(encoding="utf-8").splitlines()
    except Exception:
        return items
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if not isinstance(rec, dict) or rec.get("archived"):
            continue
        content = str(rec.get("content") or "").strip()
        if len(content) < MIN_CONTENT_LEN:
            continue
        name = str(rec.get("name") or content[:60]).strip()
        pid = rec.get("pattern_id", "")
        tags = rec.get("tags") if isinstance(rec.get("tags"), list) else []
        items.append(
            HarvestItem(
                content=content,
                name=name[:60],
                description=str(rec.get("description") or "")[:200],
                pattern_type=str(rec.get("pattern_type") or "workflow-pattern"),
                source=f"skill-learning:{pid}",
                tags=[*tags, "harvested", "skill-learning"],
            )
        )
    return items


def _build_payload(item: HarvestItem, content_hash: str, now: datetime) -> dict[str, Any]:
    """Mirror vector_memory _pattern_to_payload (+ content_hash, §26 P0)."""
    iso = now.isoformat()
    return {
        "pattern_id": _point_id(content_hash),
        "pattern_type": item.pattern_type,
        "name": item.name,
        "description": item.description,
        "content": item.content,
        "content_hash": content_hash,
        "confidence": _derive_conf(0.0, 0.0),  # Beta(7,3) prior = 0.70
        "evidence_sources": [{"source": item.source}],
        "created_at": iso,
        "updated_at": iso,
        "last_applied": None,
        "succ": 0.0,
        "fail": 0.0,
        "last_decay_at": iso,
        "expired_at": None,
        "decay_rate": 0.05,
        "application_count": 0,
        "version": 1,
        "tags": item.tags,
        "metadata": {"harvested": True, "harvest_source": item.source},
    }


def _emit_ingest_stats(stats: dict[str, Any], harvester: str | None) -> None:
    """§27 P0 D0.1 — emit per-action ingestion events to memory-ingestion.log. Fail-soft.

    One event per outcome (saved/dup/skipped/error) so the §25 analyzer / P4 dashboard
    (`aggregate_ingest_events`) can derive ingest_rate / dup_rate. Metadata only.
    """
    try:
        import sys

        src_dir = str(PROJECT_ROOT / "src")
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)
        from memory.orchestrator.ingest_metrics import record_ingest
    except Exception:
        return
    h = harvester or "ingest_items"
    created_hashes = stats.get("created_hashes") or []
    dup_hashes = stats.get("dup_hashes") or []

    def _emit_keyed(hashes: list[str], count: int, action: str) -> None:
        # §27 P3 D3.2: prefer per-item content_hash + derived pattern_id so the
        # ingestion sink shares the cross-store fact key with confidence-lifecycle
        # (which logs pattern_id) — enables `fact-trace` across both. Fall back to
        # count-only emission for callers that pass plain counts (backward-compat).
        if hashes:
            for ch in hashes:
                try:
                    record_ingest(
                        "learned_patterns",
                        action,
                        content_hash=ch,
                        pattern_id=_point_id(ch),
                        harvester=h,
                    )
                except Exception:
                    pass
        else:
            for _ in range(int(count or 0)):
                try:
                    record_ingest("learned_patterns", action, harvester=h)
                except Exception:
                    pass

    _emit_keyed(created_hashes, int(stats.get("created", 0) or 0), "saved")
    _emit_keyed(dup_hashes, int(stats.get("skipped_dup", 0) or 0), "dup")
    # Cap/error outcomes have no specific fact key — count-based.
    for stat_key, action, reason in (("skipped_cap", "skipped", "cap"), ("errors", "error", None)):
        for _ in range(int(stats.get(stat_key, 0) or 0)):
            try:
                record_ingest("learned_patterns", action, reason=reason, harvester=h)
            except Exception:
                pass


def ingest_items(
    items: list[HarvestItem],
    *,
    cap: int | None = None,
    dry_run: bool = False,
    client: Any = None,
    embed: Callable[[str], list[float] | None] | None = None,
    now: datetime | None = None,
    on_created: Callable[[HarvestItem, str], None] | None = None,
    harvester: str | None = None,
) -> dict[str, Any]:
    """Dedup (UUID5 content_hash) + cap + embed + upsert HarvestItems into learned_patterns.

    Shared ingestion core reused by ``harvest`` (P1) and the reflection job (P2 D2.1).
    Returns stats: created / skipped_dup / skipped_cap / errors / items(names).
    Pure fail-soft — never raises. ``on_created(item, point_id)`` fires after each
    successful upsert (e.g. to record DERIVES_FROM links). ``client``/``embed`` are
    injectable for tests (no live Qdrant/TEI needed).
    """
    cap = DEFAULT_CAP if cap is None else cap
    now = now or datetime.now()
    embed = embed or _passage_embed
    stats: dict[str, Any] = {
        "created": 0,
        "skipped_dup": 0,
        "skipped_cap": 0,
        "errors": 0,
        "items": [],
        # §27 P3 D3.2: per-item content_hashes so ingestion events carry the
        # cross-store fact key (+ derived pattern_id) for end-to-end fact-trace.
        "created_hashes": [],
        "dup_hashes": [],
        "dry_run": dry_run,
    }

    # de-dup candidates within this run by content_hash (cheap, pre-Qdrant)
    seen_local: set[str] = set()
    uniq: list[HarvestItem] = []
    for it in items:
        ch = it.content_hash
        if ch in seen_local:
            continue
        seen_local.add(ch)
        uniq.append(it)

    if not uniq:
        return stats

    # lazy real client only if we have something to do and none injected
    if client is None and not dry_run:
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=3)
        except Exception:
            stats["errors"] += 1
            _emit_ingest_stats(stats, harvester)
            return stats

    for it in uniq:
        if stats["created"] >= cap:
            stats["skipped_cap"] += 1
            continue
        ch = it.content_hash
        pid = _point_id(ch)
        try:
            if not dry_run and client is not None:
                existing = client.retrieve(collection_name=COLLECTION, ids=[pid])
                if existing:
                    stats["skipped_dup"] += 1
                    stats["dup_hashes"].append(ch)
                    continue
        except Exception:
            stats["errors"] += 1
            continue

        if dry_run:
            stats["created"] += 1
            stats["items"].append(it.name)
            stats["created_hashes"].append(ch)
            continue

        vec = embed(it.content)
        if not vec:
            stats["errors"] += 1
            continue
        payload = _build_payload(it, ch, now)
        try:
            from qdrant_client import models as qmodels

            client.upsert(
                collection_name=COLLECTION,
                points=[qmodels.PointStruct(id=pid, vector=vec, payload=payload)],
            )
        except Exception:
            stats["errors"] += 1
            continue
        stats["created"] += 1
        stats["items"].append(it.name)
        stats["created_hashes"].append(ch)
        if on_created is not None:
            try:
                on_created(it, pid)
            except Exception:
                pass

    if not dry_run:
        _emit_ingest_stats(stats, harvester)
        if stats["created"]:
            # §24 cache invalidation (roadmap 260609 P1.5): without a bump,
            # freshly harvested patterns stay invisible to the surfacing hook
            # for up to the full cache TTL.
            try:
                src_dir = str(PROJECT_ROOT / "src")
                if src_dir not in sys.path:
                    sys.path.append(src_dir)
                from memory.vector_memory import epoch

                epoch.bump()
            except Exception:
                pass
    return stats


def harvest(
    *,
    drafts_dir: Path = DRAFTS_DIR,
    lifecycle_dir: Path = LIFECYCLE_DIR,
    skill_learning_file: Path = SKILL_LEARNING_FILE,
    cap: int | None = None,
    dry_run: bool = False,
    sources: tuple[str, ...] = ("drafts", "lessons", "skill_learning"),
    client: Any = None,
    embed: Callable[[str], list[float] | None] | None = None,
    now: datetime | None = None,
    lesson_max_age_hours: int = 48,
) -> dict[str, Any]:
    """Harvest confirmed drafts + session-lessons + confirmed skill-learning patterns
    into learned_patterns (§26 P1 D1.1 + P2 D2.2). Delegates to ``ingest_items``.
    Pure fail-soft.
    """
    now = now or datetime.now()
    candidates: list[HarvestItem] = []
    if "drafts" in sources:
        candidates += iter_confirmed_drafts(drafts_dir)
    if "lessons" in sources:
        candidates += iter_session_lessons(lifecycle_dir, lesson_max_age_hours, now)
    if "skill_learning" in sources:
        candidates += iter_confirmed_skill_patterns(skill_learning_file)
    return ingest_items(
        candidates,
        cap=cap,
        dry_run=dry_run,
        client=client,
        embed=embed,
        now=now,
        harvester="patterns",
    )
