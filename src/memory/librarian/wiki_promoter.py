"""Thin L2→L3 promotion component for promoting learned patterns to wiki pages.

Scans Qdrant ``learned_patterns`` for high-confidence, well-used patterns,
deduplicates against existing wiki content, and creates draft pages in
``docs/wiki/drafts/`` via :pymeth:`MemoryCube.to_wiki_page`.
"""

from __future__ import annotations

import re
from pathlib import Path

from qdrant_client.models import FieldCondition, Filter, Range

from src.memory.infrastructure.conflict_resolver import ConflictResolver, ConflictStrategy
from src.memory.infrastructure.event_bus import EventBus
from src.memory.orchestrator.memcube import ContentType, MemoryCube
from src.memory.orchestrator.link_registry import LinkRegistry, LinkType
from src.memory.orchestrator.unified_id import MemoryType, SourceServer, UnifiedID
from src.memory.vector_memory.confidence import payload_effective_confidence


class WikiPromoter:
    """Scans learned patterns (L2) and promotes high-confidence ones to wiki drafts (L3)."""

    def __init__(
        self,
        qdrant_client,
        event_bus: EventBus | None = None,
        wiki_drafts_dir: Path = Path("docs/wiki/drafts"),
        wiki_log_path: Path = Path("docs/wiki/log.md"),
        confidence_threshold: float = 0.8,
        usage_threshold: int = 5,
        similarity_threshold: float = 0.85,
    ) -> None:
        self.client = qdrant_client
        self.conflict_resolver = ConflictResolver(default_strategy=ConflictStrategy.SOURCE_PRIORITY)
        self.event_bus = event_bus
        self.drafts_dir = wiki_drafts_dir
        self.wiki_log_path = wiki_log_path
        self.confidence_threshold = confidence_threshold
        # Canonical field name: `application_count` — written by
        # src/memory/vector_memory/server.py:handle_apply_pattern. Constructor
        # arg stays `usage_threshold` for back-compat with older callers and
        # spec language; on the wire we filter `application_count`.
        self.usage_threshold = usage_threshold
        self.similarity_threshold = similarity_threshold

    async def scan_and_promote(self) -> list[str]:
        """Scan eligible patterns and create wiki drafts for new ones."""
        candidates, _ = self.client.scroll(
            collection_name="learned_patterns",
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="confidence", range=Range(gte=self.confidence_threshold)),
                    FieldCondition(key="application_count", range=Range(gte=self.usage_threshold)),
                ]
            ),
            with_payload=True,
            with_vectors=True,
            limit=100,
        )
        created: list[str] = []
        for point in candidates:
            payload = point.payload or {}
            # Lazy-decay gate: stored conf≥0.8 is a valid cheap prefilter
            # (effective≥0.8 ⟹ stored≥0.8), but stale patterns whose stored
            # conf≥0.8 has decayed below threshold at read-time are skipped here.
            if payload_effective_confidence(payload) < self.confidence_threshold:
                continue
            # §22 P3: skip archived patterns (expired_at set) — invalidate-not-delete;
            # an apply() revives them, after which they become promotable again.
            if payload.get("expired_at"):
                continue
            vector = self._extract_vector(point, payload)
            existing = await self._dedup_check(vector, str(point.id))
            if existing is None:
                slug = await self._create_draft(payload)
                await self._publish_event(
                    "wiki.draft.created", {"slug": slug, "source_id": str(point.id)}
                )
                created.append(slug)
        return created

    @staticmethod
    def _extract_vector(point, payload: dict) -> list[float] | None:
        """Qdrant returns the vector in ``point.vector`` when ``with_vectors=True``.

        Named-vector collections return a dict; fall back to ``payload['vector']``
        to stay compatible with older fixtures.
        """
        vector = getattr(point, "vector", None)
        if isinstance(vector, dict):
            vector = next(iter(vector.values()), None)
        if vector:
            return list(vector)
        legacy = payload.get("vector")
        return list(legacy) if legacy else None

    async def _dedup_check(self, embedding: list[float] | None, source_id: str) -> str | None:
        if not embedding:
            return None
        results = self.client.query_points(
            collection_name="learned_patterns",
            query=embedding,
            limit=5,
            with_payload=True,
        )
        for scored in results.points:
            if str(scored.id) == source_id:
                continue
            if scored.score >= self.similarity_threshold:
                payload = scored.payload or {}
                promoted = payload.get("promoted_to")
                if promoted:
                    return promoted
                slug = self._slugify(payload.get("name", "unnamed"))
                if (self.drafts_dir / f"{slug}.md").exists():
                    return slug
        return None

    async def _create_draft(self, candidate_payload: dict) -> str:
        name = candidate_payload.get("name", "unnamed-pattern")
        slug = self._slugify(name)
        cube = MemoryCube(
            content=candidate_payload.get("content", ""),
            content_type=ContentType.WIKI,
            memory_type=MemoryType.WIKI,
            source=SourceServer.OBSIDIAN_VAULT,
            title=name,
            confidence=candidate_payload.get("confidence", 0.8),
            tags=candidate_payload.get("tags", []),
            what=candidate_payload.get("description"),
        )
        self.drafts_dir.mkdir(parents=True, exist_ok=True)
        (self.drafts_dir / f"{slug}.md").write_text(cube.to_wiki_page(), encoding="utf-8")
        self._append_log(slug, name, candidate_payload.get("confidence", 0.8))
        return slug

    def _append_log(self, slug: str, name: str, confidence: float) -> None:
        from datetime import datetime

        entry = (
            f"\n## {datetime.now().strftime('%Y-%m-%d')} — Auto-promoted: {name}\n\n"
            f"**Event:** L2 pattern promoted to wiki draft\n\n"
            f"- Pattern: `{name}` (confidence: {confidence:.2f})\n"
            f"- Draft: `docs/wiki/drafts/{slug}.md`\n\n"
            f"**Status:** Pending review\n\n---\n"
        )
        try:
            if self.wiki_log_path.exists():
                content = self.wiki_log_path.read_text(encoding="utf-8")
                # Insert before "## Format Template" section
                marker = "\n## Format Template"
                if marker in content:
                    content = content.replace(marker, entry + marker, 1)
                else:
                    content += entry
                # Trim to 500 lines
                lines = content.split("\n")
                if len(lines) > 500:
                    content = "\n".join(lines[:500])
                self.wiki_log_path.write_text(content, encoding="utf-8")
        except Exception:
            pass

    async def _publish_event(self, event_type: str, data: dict) -> None:
        if self.event_bus is not None:
            try:
                await self.event_bus.publish(event_type, data, source="wiki_promoter")
            except Exception:
                pass

    @staticmethod
    def _slugify(name: str) -> str:
        return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))[:80] or "unnamed"
