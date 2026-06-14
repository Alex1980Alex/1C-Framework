"""§26 P1 D1.2 — skills-harvester core (incremental skill_library indexing).

The batch indexer ``scripts/index-skills-to-qdrant.py`` re-embeds ALL ~80 skills
(~2-3 min) — too heavy to run on every skill edit. This helper does the same
per-skill work INCREMENTALLY and idempotently:

  - parse SKILL.md frontmatter + embed `description\\ntriggers` as a passage
    (NO query instruction — mirrors the batch indexer exactly);
  - point id = ``uuid5(NAMESPACE_URL, skill_name)`` (same scheme as the indexer,
    so incremental upserts update the very points a full rebuild manages);
  - idempotency by SKILL.md content-hash kept in a small state file — only
    changed / new skills are re-embedded;
  - **cold-start seed**: on first run (no state) the current hashes are recorded
    WITHOUT embedding (skill_library is already populated by the batch indexer),
    so we never trigger an 80-embedding storm inside an 8s Stop hook;
  - **stale-cleanup**: a skill whose SKILL.md disappeared has its point deleted;
  - per-run cap bounds Stop latency when many skills change at once (remainder
    converges over subsequent Stops).

Fail-soft: Qdrant/TEI down → stats carry ``errors``, never raises.
Reversible: the Stop-hook honours ``SKILLS_HARVEST_DISABLE=1``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "skills-harvest-state.json"
COLLECTION = "skill_library"
QDRANT_HOST = os.environ.get("QDRANT_HOST", "127.0.0.1")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080") + "/embed"
DEFAULT_CAP = 10


def parse_frontmatter(content: str) -> dict:
    """Mirror scripts/index-skills-to-qdrant.py::parse_frontmatter."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    body = content[match.end() :].strip()
    meta["content_preview"] = body[:2000]
    description = meta.get("description", "")
    triggers = ""
    for marker in ["Триггеры:", "Triggers:", "Триггеры: '", "triggers:"]:
        if marker.lower() in description.lower():
            idx = description.lower().index(marker.lower())
            triggers = description[idx + len(marker) :].strip()
            break
    meta["triggers"] = triggers
    return meta


def _passage_embed(text: str, timeout: float = 4.0) -> list[float] | None:
    """TEI /embed, passage-side (no query instruction). None on error."""
    if not text.strip():
        return None
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


def _skill_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", "replace")).hexdigest()[:16]


def _point_id(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, name))


def _load_state(state_file: Path) -> dict[str, Any]:
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state_file: Path, state: dict[str, Any]) -> None:
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, state_file)
    except Exception:
        pass


def _scan_skills(skills_dir: Path) -> dict[str, dict[str, str]]:
    """Return {skill_name: {hash, content, file}} for every SKILL.md."""
    found: dict[str, dict[str, str]] = {}
    if not skills_dir.exists():
        return found
    for md in sorted(skills_dir.glob("*/SKILL.md")):
        try:
            content = md.read_text(encoding="utf-8")
        except Exception:
            continue
        meta = parse_frontmatter(content)
        name = meta.get("name") or md.parent.name
        try:
            rel = str(md.relative_to(PROJECT_ROOT))
        except ValueError:  # skills_dir outside the repo (tests)
            rel = str(md)
        found[name] = {
            "hash": _skill_hash(content),
            "content": content,
            "file": rel.replace("\\", "/"),
        }
    return found


def _build_payload(name: str, meta: dict, rel_path: str, content_hash: str = "") -> dict[str, Any]:
    return {
        "skill_name": name,
        "file_path": rel_path,
        "description": meta.get("description", ""),
        "triggers": meta.get("triggers", ""),
        "content_preview": meta.get("content_preview", "")[:500],
        # §26 write-contract (roadmap 260612 P0.2): cross-store idempotency key —
        # sha256(SKILL.md)[:16], same algorithm as orchestrator content_hash.
        "content_hash": content_hash,
        "indexed_at": datetime.now(UTC).isoformat(),
    }


def _record_ingest(action: str, *, content_hash: str = "", harvester: str, **extra: Any) -> None:
    """§26 write-contract: log the write attempt to memory-ingestion.log. Fail-soft."""
    try:
        import sys

        src_dir = str(PROJECT_ROOT / "src")
        if src_dir not in sys.path:
            sys.path.append(src_dir)  # append, NOT insert(0) — src/shared must not shadow hooks
        from memory.orchestrator.ingest_metrics import record_ingest

        record_ingest(
            "skill_library", action, content_hash=content_hash, harvester=harvester, **extra
        )
    except Exception:
        pass


def harvest_skills(
    *,
    skills_dir: Path = SKILLS_DIR,
    state_file: Path = STATE_FILE,
    cap: int | None = None,
    client: Any = None,
    embed: Callable[[str], list[float] | None] | None = None,
) -> dict[str, Any]:
    """Incrementally upsert changed/new skills + clean up removed ones.

    Returns stats: upserted / skipped_unchanged / deleted / skipped_cap /
    errors / seeded(bool) / items. Pure fail-soft. ``client``/``embed`` are
    injectable for tests (no live Qdrant/TEI needed).
    """
    cap = DEFAULT_CAP if cap is None else cap
    embed = embed or _passage_embed
    stats: dict[str, Any] = {
        "upserted": 0,
        "skipped_unchanged": 0,
        "deleted": 0,
        "skipped_cap": 0,
        "errors": 0,
        "seeded": False,
        "items": [],
    }

    found = _scan_skills(skills_dir)
    state = _load_state(state_file)
    prev: dict[str, Any] = state.get("skills", {}) if isinstance(state, dict) else {}

    # Cold-start: skill_library already populated by the batch indexer — record
    # current hashes WITHOUT embedding, so we don't storm 80 embeds on a Stop.
    if not state.get("seeded"):
        _save_state(
            state_file,
            {
                "seeded": True,
                "skills": {n: {"hash": d["hash"], "file": d["file"]} for n, d in found.items()},
            },
        )
        stats["seeded"] = True
        stats["items"] = sorted(found.keys())
        return stats

    if client is None:
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=4)
        except Exception:
            stats["errors"] += 1
            return stats

    new_skills = dict(prev)  # mutated copy persisted at the end

    # 1. upsert changed / new (capped)
    for name, d in found.items():
        if prev.get(name, {}).get("hash") == d["hash"]:
            stats["skipped_unchanged"] += 1
            continue
        if stats["upserted"] >= cap:
            stats["skipped_cap"] += 1
            continue
        meta = parse_frontmatter(d["content"])
        embed_input = f"{meta.get('description', '')}\n{meta.get('triggers', '')}".strip()
        vec = embed(embed_input or d["content"][:1000])
        if not vec:
            stats["errors"] += 1
            _record_ingest(
                "error",
                content_hash=d["hash"],
                harvester="skills-harvester",
                skill=name,
                reason="embed_failed",
            )
            continue
        try:
            from qdrant_client import models as qmodels

            client.upsert(
                collection_name=COLLECTION,
                points=[
                    qmodels.PointStruct(
                        id=_point_id(name),
                        vector=vec,
                        payload=_build_payload(name, meta, d["file"], content_hash=d["hash"]),
                    )
                ],
            )
        except Exception:
            stats["errors"] += 1
            _record_ingest(
                "error",
                content_hash=d["hash"],
                harvester="skills-harvester",
                skill=name,
                reason="qdrant_upsert",
            )
            continue
        new_skills[name] = {"hash": d["hash"], "file": d["file"]}
        stats["upserted"] += 1
        stats["items"].append(name)
        _record_ingest("saved", content_hash=d["hash"], harvester="skills-harvester", skill=name)

    # 2. stale-cleanup: skills in state but no longer on disk
    for name in list(prev.keys()):
        if name in found:
            continue
        try:
            client.delete(collection_name=COLLECTION, points_selector=[_point_id(name)])
        except Exception:
            stats["errors"] += 1
            continue
        new_skills.pop(name, None)
        stats["deleted"] += 1
        _record_ingest("pruned", harvester="skills-harvester", skill=name, reason="skill_removed")

    _save_state(state_file, {"seeded": True, "skills": new_skills})
    if stats["upserted"] or stats["deleted"]:
        _bump_epoch()
    return stats


def _bump_epoch() -> None:
    """§24 cache invalidation (roadmap 260609 P1.5): surfacing's skill arm reads
    skill_library through the execution cache — bump so a changed/removed skill
    is visible on the next prompt. Fail-soft."""
    try:
        import sys

        src_dir = str(PROJECT_ROOT / "src")
        if src_dir not in sys.path:
            sys.path.append(src_dir)
        from memory.vector_memory import epoch

        epoch.bump()
    except Exception:
        pass


def mirror_skill_library(
    *,
    skills_dir: Path = SKILLS_DIR,
    state_file: Path = STATE_FILE,
    client: Any = None,
    embed: Callable[[str], list[float] | None] | None = None,
    apply: bool = False,
    snapshot: bool = True,
) -> dict[str, Any]:
    """Full mirror of the skills catalog into skill_library (roadmap 260612 P0.1).

    Unlike the incremental ``harvest_skills`` (state-file diff — blind to points
    that predate the state file), this reconciles against the COLLECTION itself:

      - **ghosts** (point exists, skill dir gone — e.g. deprecated `1c-mcp-toolkit`)
        are pruned; a collection snapshot is taken first (prune is irreversible);
      - **drift** (skill on disk, no point) and **changed** skills (payload
        content_hash != disk hash, incl. legacy points without content_hash)
        are re-embedded and upserted under the §26 write-contract
        (payload ``content_hash`` + ``record_ingest``);
      - unchanged points are left alone (no re-embed);
      - the harvester state file is resynced so the incremental path agrees.

    ``_archived/<skill>/SKILL.md`` never matches the ``*/SKILL.md`` scan glob,
    so archived skills count as removed — exactly the prune semantics we want.

    Dry-run (``apply=False``) returns the plan without touching anything.
    Fail-soft per item: errors counted + ingest-logged, never raises.
    """
    embed = embed or (lambda t: _passage_embed(t, timeout=30.0))
    stats: dict[str, Any] = {
        "applied": apply,
        "catalog": 0,
        "library": 0,
        "upserted": 0,
        "unchanged": 0,
        "pruned": 0,
        "errors": 0,
        "ghosts": [],
        "missing": [],
        "to_upsert": [],
        "snapshot": None,
    }

    found = _scan_skills(skills_dir)
    stats["catalog"] = len(found)

    if client is None:
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=20)
        except Exception:
            stats["errors"] += 1
            return stats

    # Reconcile against the live collection (not the state file).
    lib: dict[str, dict[str, Any]] = {}  # skill_name -> {point_id, content_hash}
    try:
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=COLLECTION,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                sname = payload.get("skill_name")
                if sname:
                    lib[sname] = {"id": p.id, "content_hash": payload.get("content_hash", "")}
            if offset is None:
                break
    except Exception:
        stats["errors"] += 1
        return stats
    stats["library"] = len(lib)

    stats["ghosts"] = sorted(set(lib) - set(found))
    # missing = на диске есть, точки нет (drift в терминах roadmap 260612);
    # to_upsert шире — включает changed (content_hash mismatch), это штатный churn.
    stats["missing"] = sorted(set(found) - set(lib))
    stats["to_upsert"] = sorted(
        name for name, d in found.items() if lib.get(name, {}).get("content_hash") != d["hash"]
    )
    stats["unchanged"] = len(found) - len(stats["to_upsert"])

    if not apply:
        return stats

    # Prune is irreversible — snapshot first ([[reference-qdrant-collection-aliases]]).
    if stats["ghosts"] and snapshot:
        try:
            snap = client.create_snapshot(collection_name=COLLECTION)
            stats["snapshot"] = getattr(snap, "name", None) or str(snap)
        except Exception:
            stats["snapshot"] = "snapshot_failed"

    for name in stats["ghosts"]:
        try:
            client.delete(collection_name=COLLECTION, points_selector=[lib[name]["id"]])
            stats["pruned"] += 1
            _record_ingest(
                "pruned",
                content_hash=lib[name].get("content_hash", ""),
                harvester="reindex_skill_library",
                skill=name,
                reason="ghost_no_catalog_dir",
            )
        except Exception:
            stats["errors"] += 1
            _record_ingest(
                "error", harvester="reindex_skill_library", skill=name, reason="qdrant_delete"
            )

    for name in stats["to_upsert"]:
        d = found[name]
        meta = parse_frontmatter(d["content"])
        embed_input = f"{meta.get('description', '')}\n{meta.get('triggers', '')}".strip()
        vec = embed(embed_input or d["content"][:1000])
        if not vec:
            stats["errors"] += 1
            _record_ingest(
                "error",
                content_hash=d["hash"],
                harvester="reindex_skill_library",
                skill=name,
                reason="embed_failed",
            )
            continue
        try:
            from qdrant_client import models as qmodels

            client.upsert(
                collection_name=COLLECTION,
                points=[
                    qmodels.PointStruct(
                        id=_point_id(name),
                        vector=vec,
                        payload=_build_payload(name, meta, d["file"], content_hash=d["hash"]),
                    )
                ],
            )
            stats["upserted"] += 1
            _record_ingest(
                "saved", content_hash=d["hash"], harvester="reindex_skill_library", skill=name
            )
        except Exception:
            stats["errors"] += 1
            _record_ingest(
                "error",
                content_hash=d["hash"],
                harvester="reindex_skill_library",
                skill=name,
                reason="qdrant_upsert",
            )

    # Resync the incremental harvester's state so both paths agree on hashes.
    _save_state(
        state_file,
        {
            "seeded": True,
            "skills": {n: {"hash": d["hash"], "file": d["file"]} for n, d in found.items()},
        },
    )
    if stats["upserted"] or stats["pruned"]:
        _bump_epoch()
    return stats
