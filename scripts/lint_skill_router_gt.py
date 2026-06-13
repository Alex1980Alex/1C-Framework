#!/usr/bin/env python3
"""Lint the skill-router ground-truth (roadmap 260613 A8).

Enforces the GT invariants documented in
``data/skill-router-ground-truth.README.md``:

  1. every case carries all 6 fields; intent/source/split from valid sets;
  2. expected_skills ⊆ catalog (skills routable via skill-router-config.json);
  3. NO leakage in the gate: source == 'transcript-router' ⇒ split == 'quarantine'
     (a router-derived label must never sit in train/test — that is the F1
     contamination this whole follow-up exists to remove);
  4. intent ∈ {informational, system} ⇒ expected_skills == [];
  5. coverage warnings: test split should have ≥1 action, ≥1 silence, ≥5 domains.

Hard violations (1-4) → exit 1 (blocking CI job ``skill-router-gt-lint``).
Coverage (5) → warnings, exit 0 (informational; test set may still be growing, A7).

Pure stdlib. ``lint_rows`` is importable for unit tests (no file/network I/O).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GT_PATH = PROJECT_ROOT / "data" / "skill-router-ground-truth.jsonl"
ROUTER_CONFIG = PROJECT_ROOT / ".claude" / "skills" / "skill-router-config.json"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

VALID_INTENTS = {"action", "informational", "system"}
VALID_SOURCES = {"spec", "human", "transcript-human", "transcript-router"}
VALID_SPLITS = {"train", "test", "quarantine"}
LEAKAGE_SOURCES = {"transcript-router"}  # must be quarantined, never train/test
REQUIRED_FIELDS = ("prompt", "expected_skills", "expected_bundles", "intent", "source", "split")
GATE_SPLITS = ("train", "test")
MIN_TEST_DOMAINS = 5


def load_catalog(
    router_config: Path = ROUTER_CONFIG, skills_dir: Path = SKILLS_DIR
) -> set[str]:
    """Routable skills = union of bundle skills/optional in skill-router-config.json
    plus on-disk skill directory names. A GT expected_skill outside this set can
    never be produced by the router (guaranteed FN), so it is a real GT error."""
    catalog: set[str] = set()
    try:
        cfg = json.loads(router_config.read_text(encoding="utf-8"))
        for bundle in cfg.get("bundles", {}).values():
            catalog.update(bundle.get("skills", []) or [])
            catalog.update(bundle.get("optional", []) or [])
    except (OSError, json.JSONDecodeError):
        pass
    try:
        for md in skills_dir.glob("*/SKILL.md"):
            catalog.add(md.parent.name)
            m = re.match(r"^---\s*\n(.*?)\n---", md.read_text(encoding="utf-8"), re.DOTALL)
            if m:
                for line in m.group(1).splitlines():
                    if line.strip().startswith("name:"):
                        catalog.add(line.split(":", 1)[1].strip().strip("\"'"))
                        break
    except OSError:
        pass
    return catalog


def lint_rows(rows: list[dict], catalog: set[str]) -> list[str]:
    """Return hard-violation messages (empty == clean). Pure; unit-testable."""
    issues: list[str] = []
    for i, r in enumerate(rows, 1):
        missing = [k for k in REQUIRED_FIELDS if k not in r]
        if missing:
            issues.append(f"line {i}: missing fields {missing}")
            continue  # can't check further without fields
        intent, src, split = r["intent"], r["source"], r["split"]
        if intent not in VALID_INTENTS:
            issues.append(f"line {i}: invalid intent {intent!r}")
        if src not in VALID_SOURCES:
            issues.append(f"line {i}: invalid source {src!r}")
        if split not in VALID_SPLITS:
            issues.append(f"line {i}: invalid split {split!r}")
        if src in LEAKAGE_SOURCES and split in GATE_SPLITS:
            issues.append(
                f"line {i}: LEAKAGE — source={src} in split={split} "
                f"(router-derived label must be quarantine): {r['prompt'][:50]!r}"
            )
        if intent in ("informational", "system") and r.get("expected_skills"):
            issues.append(
                f"line {i}: intent={intent} but expected_skills nonempty "
                f"{r.get('expected_skills')}"
            )
        for sk in r.get("expected_skills", []):
            if sk not in catalog:
                issues.append(f"line {i}: unknown skill {sk!r} (not routable / not in catalog)")
    return issues


def coverage_warnings(rows: list[dict]) -> list[str]:
    """Soft signals on the test split (non-blocking; A7 growth may still be pending)."""
    warns: list[str] = []
    test = [r for r in rows if r.get("split") == "test"]
    if not test:
        return ["test split is empty"]
    action = [r for r in test if r.get("expected_skills")]
    silence = [r for r in test if not r.get("expected_skills")]
    if not action:
        warns.append("test split has 0 action samples")
    if not silence:
        warns.append("test split has 0 silence samples")
    # домен = первый бандл, иначе первый скилл (action без бандла не схлопывать в _none)
    domains = {
        (r.get("expected_bundles") or r.get("expected_skills") or ["_none"])[0] for r in action
    }
    if len(domains) < MIN_TEST_DOMAINS:
        warns.append(f"test covers only {len(domains)} domains (<{MIN_TEST_DOMAINS})")
    if len(action) < 30:
        warns.append(f"test has {len(action)} action samples (<30 — A7 growth pending)")
    return warns


def _load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main() -> int:
    if not GT_PATH.exists():
        print(f"::error::ground-truth not found: {GT_PATH}")
        return 1
    rows = _load_rows(GT_PATH)
    catalog = load_catalog()
    issues = lint_rows(rows, catalog)
    warns = coverage_warnings(rows)

    print(f"[gt-lint] {len(rows)} cases, catalog {len(catalog)} skills")
    for w in warns:
        print(f"[gt-lint] WARN: {w}")
    if issues:
        for it in issues:
            print(f"::error::[gt-lint] {it}")
        print(f"[gt-lint] FAIL — {len(issues)} hard violation(s)")
        return 1
    print("[gt-lint] OK — schema valid, no leakage in train/test")
    return 0


if __name__ == "__main__":
    sys.exit(main())
