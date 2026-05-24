#!/usr/bin/env python3
"""CI Failure Cache + Analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".claude" / "cache"
JSONL_FILE = CACHE_DIR / "ci-failures.jsonl"
ISSUE_TAG_FILE = CACHE_DIR / "ci-failure-issues.json"
TEI_URL = "http://localhost:8080"
QDRANT_URL = "http://localhost:6333"
COLLECTION = "ci_failures"
COLLECTION_DIM = 1024
OCCURRENCE_THRESHOLD = 3
NOISE_PATTERNS = re.compile(
    r"##\[group\]|Prepare workflow|Set up Python|Install uv|Cache dependencies|"
    r"Initialize CodeQL|Post Run|safe\.directory|Cleaning up orphan|Post job cleanup",
    re.IGNORECASE)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _gh(*args: str) -> tuple[int, str, str]:
    r = subprocess.run(["gh", *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       cwd=str(PROJECT_ROOT), check=False)
    return r.returncode, r.stdout, r.stderr


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _append_jsonl(entry: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with JSONL_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl() -> list[dict]:
    if not JSONL_FILE.exists():
        return []
    out = []
    with JSONL_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def extract_first_error(log: str) -> str:
    markers = ("##[error]", "FAIL", "Error:", "error:", "Failed:", "failure")
    for raw in log.splitlines():
        line = raw.strip()
        if not line or NOISE_PATTERNS.search(line):
            continue
        line = re.sub(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+", "", line)
        line = re.sub(r"^[A-Za-z0-9 ()]+\t[A-Z ]+\t", "", line)
        for m in markers:
            if m in line:
                return line[:300]
    return "(no error line extracted)"


def fetch_failure_log(run_id: str, job_name: str | None = None) -> str:
    rc, out, _ = _gh("run", "view", str(run_id), "--log-failed")
    if rc != 0 or not out.strip():
        return ""
    if job_name:
        return "\n".join(ln for ln in out.splitlines() if job_name in ln)
    return out


def _mrl_truncate(vec: list[float], dim: int) -> list[float]:
    if len(vec) <= dim:
        return vec
    vec = vec[:dim]
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec] if norm > 1e-9 else vec


def _embed_tei(text: str) -> list[float] | None:
    try:
        import httpx
    except ImportError:
        return None
    prefix = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
    try:
        with httpx.Client(base_url=TEI_URL, timeout=3.0) as c:
            r = c.post("/embed", json={"inputs": [prefix + text], "normalize": True, "truncate": True})
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    return _parse_embedding(data)
