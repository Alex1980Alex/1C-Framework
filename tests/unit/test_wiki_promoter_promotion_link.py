"""Unit tests for WikiPromoter PROMOTED_TO links (§26 P3, D3.3).

Promotion learned_pattern -> wiki draft must record a PROMOTED_TO edge in the
link_registry (provenance, not a second orphaned copy), idempotently, and be a
no-op when no registry is wired (backward compatibility).
"""

from __future__ import annotations

import pytest

from src.memory.librarian.wiki_promoter import WikiPromoter
from src.memory.orchestrator.link_registry import LinkRegistry, LinkType

pytestmark = pytest.mark.unit


def _promoter(tmp_path) -> tuple[WikiPromoter, LinkRegistry]:
    reg = LinkRegistry(db_path=str(tmp_path / "links.db"))
    # qdrant_client unused by _create_promotion_link -> None is fine here
    return WikiPromoter(qdrant_client=None, link_registry=reg), reg


def test_promotion_creates_promoted_to_link(tmp_path):
    wp, reg = _promoter(tmp_path)
    wp._create_promotion_link("pt1", "my-slug")
    link = reg.find_link(
        "semantic:vector-memory:pt1", "wiki:obsidian-vault:my-slug", LinkType.PROMOTED_TO
    )
    assert link is not None
    assert link.link_type == LinkType.PROMOTED_TO
    assert link.metadata.get("slug") == "my-slug"


def test_promotion_link_idempotent(tmp_path):
    wp, reg = _promoter(tmp_path)
    wp._create_promotion_link("pt1", "my-slug")
    wp._create_promotion_link("pt1", "my-slug")  # second call must not duplicate
    links = reg.get_links_from("semantic:vector-memory:pt1", [LinkType.PROMOTED_TO])
    assert len(links) == 1


def test_no_registry_is_noop():
    wp = WikiPromoter(qdrant_client=None, link_registry=None)
    # must not raise when promotion linking is disabled
    wp._create_promotion_link("pt1", "my-slug")
