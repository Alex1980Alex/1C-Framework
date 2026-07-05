"""Live counters for docs "drift" detection (roadmap 260704 P3.1).

Docs like CLAUDE.md / chapter files carry hand-written numbers ("57 скиллов /
25 бандлов / 27 серверов") that silently go stale as the framework grows.
This script computes the *live* counters from the actual repo anchors
(`.claude/skills/`, `skill-router-config.json`, `.mcp.json`,
`infra/lazy-mcp/config/registry.yaml`, `.claude/hooks/`) and can optionally
scan docs for mentions of these counters to flag mismatches.

Usage:
    python scripts/docs_counters.py --json
    python scripts/docs_counters.py --check [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a declared project dependency
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parents[1]

# Directories/filenames excluded from the drift scan: historical numbers in
# roadmaps/changelogs/worktrees are legitimate and would just be noise.
_EXCLUDE_PATH_TOKENS = ("worktrees", "roadmap")
_EXCLUDE_NAME_TOKENS = ("changelog", "дорожная")

# word (число) or (число) word, single-line context window
_COUNTER_KEYWORDS = r"(?:скилл\w*|бандл\w*|bundle\w*|MCP[- ]сервер\w*|хук\w*)"
_PATTERN_NUM_THEN_WORD = re.compile(r"(?P<num>\d+)\s*" + _COUNTER_KEYWORDS, re.IGNORECASE)
_PATTERN_WORD_THEN_NUM = re.compile(
    _COUNTER_KEYWORDS + r"[^\d\n\]/#]{0,10}[:\-]?\s*(?P<num>\d+)", re.IGNORECASE
)


def count_skills(root: Path) -> int:
    """Count subdirectories of .claude/skills/ that contain a SKILL.md file."""
    skills_dir = root / ".claude" / "skills"
    if not skills_dir.is_dir():
        return 0
    return sum(1 for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").is_file())


def count_bundles(root: Path) -> tuple[int, Any]:
    """Return (bundles_total, router_config_version) from skill-router-config.json."""
    config_path = root / ".claude" / "skills" / "skill-router-config.json"
    if not config_path.is_file():
        return 0, None
    data = json.loads(config_path.read_text(encoding="utf-8"))
    bundles = data.get("bundles", {})
    return len(bundles), data.get("version")


def count_mcp_servers(root: Path) -> int:
    """Count keys under mcpServers in the root .mcp.json."""
    mcp_path = root / ".mcp.json"
    if not mcp_path.is_file():
        return 0
    data = json.loads(mcp_path.read_text(encoding="utf-8"))
    return len(data.get("mcpServers", {}))


def count_lazy_mcp(root: Path) -> tuple[int, int]:
    """Return (lazy_mcp_servers_total, lazy_mcp_categories_total)."""
    registry_path = root / "infra" / "lazy-mcp" / "config" / "registry.yaml"
    if not registry_path.is_file() or yaml is None:
        return 0, 0
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    categories = data.get("categories", {}) or {}
    servers_total = sum(len((cat or {}).get("servers", {}) or {}) for cat in categories.values())
    return servers_total, len(categories)


def count_hooks(root: Path) -> int:
    """Count *.py files directly in .claude/hooks/ (excludes shared/ subdir)."""
    hooks_dir = root / ".claude" / "hooks"
    if not hooks_dir.is_dir():
        return 0
    return sum(1 for f in hooks_dir.glob("*.py") if f.is_file())


def probe_qdrant_collections(timeout: float = 2.0) -> int | None:
    """Best-effort GET http://localhost:6333/collections; None if unavailable."""
    try:
        with urllib.request.urlopen("http://localhost:6333/collections", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        collections = payload.get("result", {}).get("collections", [])
        return len(collections)
    except Exception:
        return None


def collect_counters(root: Path) -> dict[str, Any]:
    bundles_total, router_config_version = count_bundles(root)
    lazy_mcp_servers_total, lazy_mcp_categories_total = count_lazy_mcp(root)
    return {
        "skills_total": count_skills(root),
        "bundles_total": bundles_total,
        "router_config_version": router_config_version,
        "mcp_servers_total": count_mcp_servers(root),
        "lazy_mcp_servers_total": lazy_mcp_servers_total,
        "lazy_mcp_categories_total": lazy_mcp_categories_total,
        "hooks_files_total": count_hooks(root),
        "qdrant_collections": probe_qdrant_collections(),
    }


def _is_excluded(path: Path) -> bool:
    parts_lower = [p.lower() for p in path.parts]
    for token in _EXCLUDE_PATH_TOKENS:
        if any(token in part for part in parts_lower):
            return True
    name_lower = path.name.lower()
    return any(token in name_lower for token in _EXCLUDE_NAME_TOKENS)


def _candidate_files(root: Path) -> list[Path]:
    files: list[Path] = []
    docs_dir = root / "docs" / "framework documentation"
    if docs_dir.is_dir():
        files.extend(docs_dir.rglob("*.md"))
    skills_dir = root / ".claude" / "skills"
    if skills_dir.is_dir():
        files.extend(skills_dir.glob("*/SKILL.md"))
    return [f for f in files if not _is_excluded(f)]


# Maps a doc-mention keyword (lowercased) to the corresponding live counter key.
_KEYWORD_TO_COUNTER = {
    "скилл": "skills_total",
    "бандл": "bundles_total",
    "bundle": "bundles_total",
    "хук": "hooks_files_total",
}


def _counter_key_for_match(word_context: str) -> str | None:
    lower = word_context.lower()
    if "mcp" in lower and ("сервер" in lower or "server" in lower):
        return "mcp_servers_total"
    for kw, counter_key in _KEYWORD_TO_COUNTER.items():
        if kw in lower:
            return counter_key
    return None


def scan_drift(root: Path, live: dict[str, Any]) -> list[dict[str, Any]]:
    """Scan candidate docs for stale counter mentions vs. live values."""
    mismatches: list[dict[str, Any]] = []
    for path in _candidate_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel = path.relative_to(root)
        for line_no, line in enumerate(text.splitlines(), start=1):
            for pattern in (_PATTERN_NUM_THEN_WORD, _PATTERN_WORD_THEN_NUM):
                for m in pattern.finditer(line):
                    found_num = int(m.group("num"))
                    counter_key = _counter_key_for_match(m.group(0))
                    if counter_key is None:
                        continue
                    live_value = live.get(counter_key)
                    if live_value is None or found_num == live_value:
                        continue
                    mismatches.append(
                        {
                            "file": str(rel),
                            "line": line_no,
                            "found": found_num,
                            "live": live_value,
                            "context": m.group(0).strip(),
                            "counter": counter_key,
                        }
                    )
    return mismatches


def _print_utf8(text: str) -> None:
    sys.stdout.buffer.write(text.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print live counters as JSON")
    parser.add_argument(
        "--check", action="store_true", help="Scan docs for drifted counter mentions"
    )
    parser.add_argument(
        "--strict", action="store_true", help="Exit 1 if drift found (default advisory, exit 0)"
    )
    args = parser.parse_args()

    live = collect_counters(REPO_ROOT)

    if args.json or not args.check:
        _print_utf8(json.dumps(live, ensure_ascii=False, indent=2) + "\n")

    if not args.check:
        return 0

    mismatches = scan_drift(REPO_ROOT, live)
    if not mismatches:
        _print_utf8("No counter drift detected.\n")
        return 0

    lines = [f"Found {len(mismatches)} potential counter drift(s):\n"]
    lines.append(f"{'file:line':<70} | {'found':>6} | {'live':>6} | context\n")
    for m in mismatches:
        loc = f"{m['file']}:{m['line']}"
        lines.append(f"{loc:<70} | {m['found']:>6} | {str(m['live']):>6} | {m['context']}\n")
    _print_utf8("".join(lines))

    return 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
