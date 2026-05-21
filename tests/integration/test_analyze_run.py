"""Smoke test for ``scripts/analyze_run.py`` and ``scripts/analyzers/``.

Verifies the analyzer can be invoked on a synthetic progress JSONL fixture,
gracefully handles Qdrant unavailability, and produces a Markdown + JSON
report under the requested output directory.

Does NOT require a live Qdrant — the analyzer's collection-introspection
section reports "Qdrant introspection failed" without crashing when the
URL is unreachable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ANALYZE_SCRIPT = REPO_ROOT / "scripts" / "analyze_run.py"


@pytest.fixture
def synthetic_run(tmp_path: Path) -> tuple[Path, Path, str]:
    """Build a tmp progress JSONL with a complete fake run and return paths."""
    jsonl = tmp_path / "progress.jsonl"
    reports = tmp_path / "reports"
    run_id = "smoke-test-run-42"
    events = [
        {
            "ts": "2026-05-22T00:00:00+03:00",
            "run_id": run_id,
            "script": "fake_indexer",
            "category": "run_start",
            "elapsed_s": 0.0,
            "pid": 12345,
        },
        {
            "ts": "2026-05-22T00:00:00+03:00",
            "run_id": run_id,
            "script": "fake_indexer",
            "category": "event",
            "elapsed_s": 0.001,
            "name": "startup",
            "collection": "fake_collection",
            "batch_size": 16,
        },
        {
            "ts": "2026-05-22T00:00:01+03:00",
            "run_id": run_id,
            "script": "fake_indexer",
            "category": "stage_start",
            "elapsed_s": 0.001,
            "name": "model_load",
        },
        {
            "ts": "2026-05-22T00:00:02+03:00",
            "run_id": run_id,
            "script": "fake_indexer",
            "category": "stage_end",
            "elapsed_s": 1.0,
            "name": "model_load",
            "ok": True,
            "err": None,
        },
        {
            "ts": "2026-05-22T00:00:10+03:00",
            "run_id": run_id,
            "script": "fake_indexer",
            "category": "run_end",
            "elapsed_s": 10.0,
            "files": 5,
            "symbols": 20,
            "chunks": 30,
            "errors": 0,
            "collection": "fake_collection",
        },
    ]
    with jsonl.open("w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    return jsonl, reports, run_id


def test_analyze_run_indexing_smoke(synthetic_run: tuple[Path, Path, str]) -> None:
    jsonl, reports, run_id = synthetic_run

    proc = subprocess.run(
        [
            sys.executable,
            str(ANALYZE_SCRIPT),
            "--mode",
            "indexing",
            "--run-id",
            run_id,
            "--progress-jsonl",
            str(jsonl),
            "--reports-dir",
            str(reports),
            "--qdrant-url",
            "http://localhost:0",
            "--sample-size",
            "10",
            "--json-only",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert proc.returncode == 0, f"analyzer failed: stderr={proc.stderr!r}"

    out = json.loads(proc.stdout.strip())
    assert out["ok"] is True
    assert out["mode"] == "indexing"
    assert out["subject"] == "fake_collection"
    assert out["run_id"] == run_id

    md_path = Path(out["md"])
    json_path = Path(out["json"])
    assert md_path.is_file()
    assert json_path.is_file()

    md = md_path.read_text(encoding="utf-8")
    assert "Indexing report" in md
    assert "Run identity & CLI" in md
    assert "Stages & timing" in md
    assert "Collection state" in md
    assert "fake_collection" in md
    assert "Qdrant introspection failed" in md or "не удалось" in md.lower()

    raw = json.loads(json_path.read_text(encoding="utf-8"))
    assert raw["collection"] == "fake_collection"
    assert raw["run_end"]["files"] == 5
    assert raw["events_total"] == 5


def test_analyze_run_missing_runid(tmp_path: Path) -> None:
    """analyzer must exit non-zero if --run-id is omitted for indexing mode."""
    proc = subprocess.run(
        [
            sys.executable,
            str(ANALYZE_SCRIPT),
            "--mode",
            "indexing",
            "--progress-jsonl",
            str(tmp_path / "missing.jsonl"),
            "--reports-dir",
            str(tmp_path / "reports"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode != 0
    assert "run-id required" in proc.stderr.lower() or "run_id required" in proc.stderr.lower()


def test_analyze_run_unknown_runid(tmp_path: Path) -> None:
    """analyzer must exit 1 if run_id has no matching events."""
    jsonl = tmp_path / "empty.jsonl"
    jsonl.write_text("", encoding="utf-8")
    proc = subprocess.run(
        [
            sys.executable,
            str(ANALYZE_SCRIPT),
            "--mode",
            "indexing",
            "--run-id",
            "does-not-exist",
            "--progress-jsonl",
            str(jsonl),
            "--reports-dir",
            str(tmp_path / "reports"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 1
    assert "No events found" in proc.stderr
