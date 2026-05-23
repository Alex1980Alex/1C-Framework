"""Unit tests for archive-stale CLI subcommand (added 2026-05-15).

Coverage:
    - Filters by max_age_days
    - Filters by min_confidence
    - Skips status=archived pages
    - Skips pages without frontmatter
    - Uniqueness suffix on target collision
    - Dry-run does not move files
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def _make_args(wiki_dir, archive_dir, *, max_age_days=365, min_confidence=0.3, dry_run=False):
    return argparse.Namespace(
        wiki_dir=wiki_dir,
        archive_dir=archive_dir,
        max_age_days=max_age_days,
        min_confidence=min_confidence,
        dry_run=dry_run,
        verbose=False,
    )


def _make_page(wiki_dir: Path, name: str, status: str, confidence: float,
               updated_at: datetime) -> Path:
    page = wiki_dir / f"{name}.md"
    page.write_text(
        f"---\n"
        f"unified_id: 019e1234-5678-7e2a-9f1b-{name.replace('-', '')[:12]}\n"
        f"status: {status}\n"
        f"tags:\n  - test\n"
        f"related:\n  - '[[_index]]'\n"
        f"created_at: {updated_at.isoformat()}\n"
        f"updated_at: {updated_at.isoformat()}\n"
        f"confidence: {confidence}\n"
        f"---\n\n"
        f"# {name}\n\nbody\n",
        encoding="utf-8",
    )
    return page


@pytest.fixture
def wiki_dirs(tmp_path):
    wiki_dir = tmp_path / "entities"
    archive_dir = tmp_path / "archive"
    wiki_dir.mkdir()
    return wiki_dir, archive_dir


@pytest.mark.asyncio
async def test_archive_stale_archives_qualifying_page(wiki_dirs):
    """Page: status=active, confidence<0.3, updated_at older than 365d → archived."""
    wiki_dir, archive_dir = wiki_dirs
    old = datetime.now() - timedelta(days=400)
    page = _make_page(wiki_dir, "stale-1", "active", 0.2, old)

    from scripts.export_graph_to_wiki import cmd_archive_stale
    args = _make_args(wiki_dir, archive_dir)
    rc = await cmd_archive_stale(args)
    assert rc == 0
    assert not page.exists()
    target_dir = archive_dir / datetime.now().strftime("%Y-%m")
    assert (target_dir / "stale-1.md").exists()


@pytest.mark.asyncio
async def test_archive_stale_skips_recent_page(wiki_dirs):
    """Page updated yesterday — NOT archived (too fresh)."""
    wiki_dir, archive_dir = wiki_dirs
    fresh = datetime.now() - timedelta(days=1)
    page = _make_page(wiki_dir, "fresh", "active", 0.2, fresh)

    from scripts.export_graph_to_wiki import cmd_archive_stale
    args = _make_args(wiki_dir, archive_dir, max_age_days=365)
    await cmd_archive_stale(args)
    assert page.exists()


@pytest.mark.asyncio
async def test_archive_stale_skips_high_confidence(wiki_dirs):
    """Page with confidence>=0.3 — NOT archived even if old."""
    wiki_dir, archive_dir = wiki_dirs
    old = datetime.now() - timedelta(days=400)
    page = _make_page(wiki_dir, "high-conf", "active", 0.5, old)

    from scripts.export_graph_to_wiki import cmd_archive_stale
    args = _make_args(wiki_dir, archive_dir, min_confidence=0.3)
    await cmd_archive_stale(args)
    assert page.exists()


@pytest.mark.asyncio
async def test_archive_stale_skips_already_archived(wiki_dirs):
    """Page with status=archived — skipped (already done)."""
    wiki_dir, archive_dir = wiki_dirs
    old = datetime.now() - timedelta(days=400)
    page = _make_page(wiki_dir, "already-archived", "archived", 0.2, old)

    from scripts.export_graph_to_wiki import cmd_archive_stale
    args = _make_args(wiki_dir, archive_dir)
    await cmd_archive_stale(args)
    assert page.exists()


@pytest.mark.asyncio
async def test_archive_stale_skips_missing_frontmatter(wiki_dirs):
    """Page without YAML frontmatter — skipped (no metadata to evaluate)."""
    wiki_dir, archive_dir = wiki_dirs
    page = wiki_dir / "no-frontmatter.md"
    page.write_text("Just plain content.\n", encoding="utf-8")

    from scripts.export_graph_to_wiki import cmd_archive_stale
    args = _make_args(wiki_dir, archive_dir)
    await cmd_archive_stale(args)
    assert page.exists()


@pytest.mark.asyncio
async def test_archive_stale_collision_uniqueness_suffix(wiki_dirs):
    """When target file already exists in archive — append .HHMMSS suffix."""
    wiki_dir, archive_dir = wiki_dirs
    old = datetime.now() - timedelta(days=400)

    target_dir = archive_dir / datetime.now().strftime("%Y-%m")
    target_dir.mkdir(parents=True)
    pre_existing = target_dir / "duplicate.md"
    pre_existing.write_text("---\nstatus: archived\n---\nold version\n", encoding="utf-8")

    page = _make_page(wiki_dir, "duplicate", "active", 0.1, old)

    from scripts.export_graph_to_wiki import cmd_archive_stale
    args = _make_args(wiki_dir, archive_dir)
    await cmd_archive_stale(args)

    # Both pre-existing and new (with suffix) must exist
    assert pre_existing.exists()
    suffixed = list(target_dir.glob("duplicate.*.md"))
    assert len(suffixed) == 1, f"Expected one suffixed file, found: {list(target_dir.iterdir())}"


@pytest.mark.asyncio
async def test_archive_stale_dry_run(wiki_dirs):
    """dry_run=True — no actual move."""
    wiki_dir, archive_dir = wiki_dirs
    old = datetime.now() - timedelta(days=400)
    page = _make_page(wiki_dir, "dry-test", "active", 0.2, old)

    from scripts.export_graph_to_wiki import cmd_archive_stale
    args = _make_args(wiki_dir, archive_dir, dry_run=True)
    rc = await cmd_archive_stale(args)
    assert rc == 0
    assert page.exists()
    # Target dir should not even be created
    target_dir = archive_dir / datetime.now().strftime("%Y-%m")
    assert not target_dir.exists() or not any(target_dir.iterdir())
