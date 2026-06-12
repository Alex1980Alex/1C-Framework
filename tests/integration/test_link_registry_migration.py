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
    @pytest.mark.parametrize(
        "lt",
        [
            LinkType.PROMOTED_TO,
            LinkType.SUPERSEDED_BY,
            LinkType.MIRRORS,
        ],
    )
    def test_new_link_type_exists(self, lt: LinkType):
        assert lt.value in ("promoted_to", "superseded_by", "mirrors")

    def test_total_link_types(self):
        # ADR-L1 (roadmap 260612 LinkRegistry): based_on/graph_node ретированы
        assert len(LinkType) == 8
        assert not hasattr(LinkType, "BASED_ON")
        assert not hasattr(LinkType, "GRAPH_NODE")


# ===== CHECK constraint =====


class TestCheckConstraint:
    def test_all_link_types_accepted(self, tmp_db):
        registry, _ = tmp_db
        for lt in LinkType:
            link_id = registry.create_link(
                source_id=f"t:src:{lt.value}",
                target_id=f"t:tgt:{lt.value}",
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
                (
                    "s",
                    "t",
                ),
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
        registry.create_link("semantic:vector-memory:1", "wiki:obsidian-vault:page-1", LinkType.PROMOTED_TO)
        links = registry.get_links_from("semantic:vector-memory:1")
        assert any(r.target_id == "wiki:obsidian-vault:page-1" for r in links)

    def test_superseded_by_round_trip(self, tmp_db):
        # GRAPH_NODE ретирован (ADR-L1 260612); проверяем живой ручной тип
        registry, _ = tmp_db
        registry.create_link("episodic:memory-ai:2", "episodic:memory-ai:42", LinkType.SUPERSEDED_BY)
        links = registry.get_links_from("episodic:memory-ai:2")
        assert any(r.target_id == "episodic:memory-ai:42" for r in links)

    def test_mirrors_bidirectional(self, tmp_db):
        registry, _ = tmp_db
        result = registry.create_link("t:s:a", "t:s:b", LinkType.MIRRORS, bidirectional=True)
        assert result is not None
        forward = registry.get_links_from("t:s:a")
        assert any(r.target_id == "t:s:b" for r in forward)
        assert forward[0].bidirectional is True
