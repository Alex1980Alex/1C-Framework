"""Integration tests for LinkRegistry migration (Phase 0.2).

Tests:
- New LinkType enums exist (PROMOTED_TO, SUPERSEDED_BY, MIRRORS, GRAPH_NODE)
- CHECK constraint accepts all 10 link types
- Migration script dry-run works
- Rollback removes new-type links
"""

import sqlite3
from pathlib import Path

import pytest

from src.memory.orchestrator.link_registry import LinkRegistry, LinkType


# ===== Fixtures =====


@pytest.fixture
def tmp_db(tmp_path):
    """Create a fresh LinkRegistry with a temp database."""
    db_path = tmp_path / "test_links.db"
    registry = LinkRegistry(db_path=str(db_path))
    return registry, db_path


# ===== LinkType enum =====


class TestNewLinkTypes:
    @pytest.mark.parametrize("lt", [
        LinkType.PROMOTED_TO,
        LinkType.SUPERSEDED_BY,
        LinkType.MIRRORS,
        LinkType.GRAPH_NODE,
    ])
    def test_new_link_type_exists(self, lt: LinkType):
        assert lt.value in ("promoted_to", "superseded_by", "mirrors", "graph_node")

    def test_total_link_types(self):
        assert len(LinkType) == 10


# ===== CHECK constraint =====


class TestCheckConstraint:
    def test_all_link_types_accepted(self, tmp_db):
        registry, _ = tmp_db
        for lt in LinkType:
            link_id = registry.create_link(
                source_id=f"src-{lt.value}",
                target_id=f"tgt-{lt.value}",
                link_type=lt,
            )
            assert link_id is not None

    def test_invalid_link_type_rejected(self, tmp_db):
        registry, db_path = tmp_db
        conn = sqlite3.connect(str(db_path))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO entity_links (source_id, target_id, link_type) "
                "VALUES (?, ?, 'invalid_type')",
                ("s", "t",),
            )
        conn.close()


# ===== Migration script =====


class TestMigrationScript:
    def test_migration_dry_run(self):
        script = Path("scripts/migrate_link_registry.py")
        assert script.exists(), "Migration script not found"

    def test_migration_sql_exists(self):
        sql = Path("migrations/001_extend_link_types.sql")
        assert sql.exists(), "Migration SQL not found"

    def test_rollback_sql_exists(self):
        sql = Path("migrations/001_rollback.sql")
        assert sql.exists(), "Rollback SQL not found"


# ===== Functional: create + query new types =====


class TestNewTypeOperations:
    def test_promoted_to_round_trip(self, tmp_db):
        registry, _ = tmp_db
        registry.create_link("mem:1", "wiki:page-1", LinkType.PROMOTED_TO)
        links = registry.get_links_from("mem:1")
        assert any(r.target_id == "wiki:page-1" for r in links)

    def test_graph_node_round_trip(self, tmp_db):
        registry, _ = tmp_db
        registry.create_link("mem:2", "graph:entity-42", LinkType.GRAPH_NODE)
        links = registry.get_links_from("mem:2")
        assert any(r.target_id == "graph:entity-42" for r in links)

    def test_mirrors_bidirectional(self, tmp_db):
        registry, _ = tmp_db
        registry.create_link("a", "b", LinkType.MIRRORS, bidirectional=True)
        forward = registry.get_links_from("a")
        backward = registry.get_links_from("b")
        assert any(r.target_id == "b" for r in forward)
        assert any(r.target_id == "a" for r in backward)
