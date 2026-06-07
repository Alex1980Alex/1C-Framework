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


def _build_payload(name: str, meta: dict, rel_path: str) -> dict[str, Any]:
    return {
        "skill_name": name,
        "file_path": rel_path,
        "description": meta.get("description", ""),
        "triggers": meta.get("triggers", ""),
        "content_preview": meta.get("content_preview", "")[:500],
        "indexed_at": datetime.now(UTC).isoformat(),
    }


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
            continue
        try:
            from qdrant_client import models as qmodels

            client.upsert(
                collection_name=COLLECTION,
                points=[
                    qmodels.PointStruct(
                        id=_point_id(name),
                        vector=vec,
                        payload=_build_payload(name, meta, d["file"]),
                    )
                ],
            )
        except Exception:
            stats["errors"] += 1
            continue
        new_skills[name] = {"hash": d["hash"], "file": d["file"]}
        stats["upserted"] += 1
        stats["items"].append(name)

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

    _save_state(state_file, {"seeded": True, "skills": new_skills})
    return stats
