"""Wiki Exporter — PDF → Structured Wiki Pages (Hermes Phase 4).

Exports GraphStore entities to canonical markdown wiki pages.
Reads from existing LightRAG GraphStore (Phase 38), generates pages
via MemoryCube.to_wiki_page() (Phase 0), maintains bidirectional links.

Includes:
- WikiExporter: core entity→page export
- ForwardSyncService: graph→wiki sync
- IncrementalWikiSync: event-driven incremental sync
- ReverseSyncService: wiki→graph reverse sync
- WikiSearchIndexer: HybridSearchService integration

Spec: openspec/changes/hermes-llm-wiki/specs/wiki-export-pipeline/spec.md
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from src.memory.orchestrator.memcube import ContentType, MemoryCube
from src.memory.orchestrator.unified_id import MemoryType, SourceServer
from src.pdf_framework.graph_store.base import BaseGraphStore
from src.pdf_framework.schemas.entities import Entity, Relation

try:
    from src.memory.infrastructure.metrics import get_metrics_collector
    _metrics = get_metrics_collector()
except ImportError:
    _metrics = None

logger = logging.getLogger(__name__)

# --- Config & Result dataclasses ---


@dataclass
class WikiExportConfig:
    output_dir: Path = field(default_factory=lambda: Path("docs/wiki/entities"))
    templates_dir: Path = field(default_factory=lambda: Path("docs/wiki/templates"))
    batch_size: int = 50
    overwrite_existing: bool = False
    include_relations: bool = True
    include_communities: bool = True
    dry_run: bool = False


@dataclass
class ExportResult:
    total_entities: int = 0
    exported_pages: int = 0
    skipped_pages: int = 0
    failed_pages: int = 0
    errors: list[dict[str, str]] = field(default_factory=list)
    duration_seconds: float = 0.0

    def summary(self) -> str:
        return (
            f"ExportResult(total={self.total_entities}, exported={self.exported_pages}, "
            f"skipped={self.skipped_pages}, failed={self.failed_pages}, "
            f"duration={self.duration_seconds:.1f}s)"
        )


class WikiExportError(Exception):
    def __init__(self, entity_id: str, reason: str) -> None:
        self.entity_id = entity_id
        self.reason = reason
        super().__init__(f"Wiki export failed for {entity_id}: {reason}")


# --- Forward Sync data ---


@dataclass
class EntityPage:
    entity_id: str
    entity_type: str
    title: str
    content: str
    frontmatter: dict[str, Any]
    relations: list[dict[str, str]]
    communities: list[str]
    source_graph: str = "lightrag_v38"
    generated_at: datetime = field(default_factory=datetime.now)


# --- Incremental Sync events ---


class GraphEventType(str, Enum):
    ENTITY_CREATED = "entity_created"
    ENTITY_UPDATED = "entity_updated"
    ENTITY_DELETED = "entity_deleted"
    RELATION_ADDED = "relation_added"
    RELATION_REMOVED = "relation_removed"
    COMMUNITY_MERGED = "community_merged"


@dataclass
class GraphChangeEvent:
    event_type: GraphEventType
    entity_id: str
    timestamp: datetime
    affected_entity_ids: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Reverse Sync data ---


@dataclass
class WikiPageChange:
    entity_id: str
    page_path: Path
    change_type: str  # "created" | "modified" | "deleted"
    frontmatter: dict[str, Any]
    content_diff: str | None = None
    added_links: list[str] = field(default_factory=list)
    removed_links: list[str] = field(default_factory=list)


# =========================================================================
# WikiExporter — core component (REQ-1)
# =========================================================================


class WikiExporter:
    """Exports GraphStore entities to canonical markdown wiki pages."""

    def __init__(
        self,
        graph_store: BaseGraphStore,
        config: WikiExportConfig | None = None,
    ) -> None:
        self._graph_store = graph_store
        self._config = config or WikiExportConfig()
        self._lock = asyncio.Lock()

    async def export_all(self) -> ExportResult:
        """Export all entities from GraphStore to wiki pages."""
        start = time.monotonic()
        result = ExportResult()

        self._config.output_dir.mkdir(parents=True, exist_ok=True)

        # Iterate all entity nodes
        graph = getattr(self._graph_store, "_graph", None)
        if graph is None:
            result.errors.append({"reason": "graph_store_unavailable", "detail": "No _graph attribute"})
            result.duration_seconds = time.monotonic() - start
            return result

        entity_ids = [
            nid for nid, data in graph.nodes(data=True)
            if data.get("node_type") != "COMMUNITY" and data.get("name")
        ]
        result.total_entities = len(entity_ids)

        # Process in batches
        for i in range(0, len(entity_ids), self._config.batch_size):
            batch = entity_ids[i : i + self._config.batch_size]
            batch_result = await self.export_batch(batch)
            result.exported_pages += batch_result.exported_pages
            result.skipped_pages += batch_result.skipped_pages
            result.failed_pages += batch_result.failed_pages
            result.errors.extend(batch_result.errors)

        result.duration_seconds = time.monotonic() - start
        logger.info("[WIKI-EXPORT] %s", result.summary())
        return result

    async def export_entity(self, entity_id: str) -> Path | None:
        """Export single entity to wiki page."""
        entity = await self._graph_store.get_entity(entity_id)
        if entity is None:
            logger.warning("[WIKI-EXPORT] Entity not found: %s", entity_id)
            return None

        cube = self._entity_to_cube(entity)

        # Add relations as wiki-links
        if self._config.include_relations:
            relations = await self._get_entity_relations(entity_id)
            wiki_links = self._generate_wiki_links(entity_id, relations)
            if wiki_links:
                cube.metadata["wiki_links"] = wiki_links
                cube.where = "\n".join(f"- {link}" for link in wiki_links)

        page_content = cube.to_wiki_page()

        if self._config.dry_run:
            logger.info("[WIKI-EXPORT] DRY RUN: would write %s", entity_id)
            return None

        # Sanitize filename
        filename = self._sanitize_filename(entity.name or entity_id)
        output_path = self._config.output_dir / f"{filename}.md"

        async with self._lock:
            if output_path.exists() and not self._config.overwrite_existing:
                logger.debug("[WIKI-EXPORT] Skip existing: %s", output_path)
                return output_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(page_content, encoding="utf-8")

        return output_path

    async def export_batch(self, entity_ids: list[str]) -> ExportResult:
        """Export batch of entities."""
        result = ExportResult(total_entities=len(entity_ids))
        for eid in entity_ids:
            try:
                path = await self.export_entity(eid)
                if path:
                    result.exported_pages += 1
                else:
                    result.skipped_pages += 1
            except WikiExportError as exc:
                result.failed_pages += 1
                result.errors.append({"entity_id": eid, "reason": exc.reason})
            except Exception as exc:
                result.failed_pages += 1
                result.errors.append({"entity_id": eid, "reason": str(exc)})
        return result

    def _entity_to_cube(self, entity: Entity) -> MemoryCube:
        """Build MemoryCube(content_type=WIKI) from GraphStore entity."""
        return MemoryCube(
            content=entity.name,
            content_type=ContentType.WIKI,
            memory_type=MemoryType.SEMANTIC,
            source=SourceServer.MEMORY_AI,
            title=entity.name or entity.id,
            confidence=entity.confidence,
            tags=["entity", entity.entity_type.lower()],
            metadata={
                "entity_id": entity.id,
                "entity_type": entity.entity_type,
                "source_document_id": entity.source_document_id,
                "source_graph": "lightrag_v38",
                "properties": entity.properties,
            },
            what=entity.name,
            why=f"Entity of type {entity.entity_type} extracted from {entity.source_document_id}",
            where=f"docs/wiki/entities/{self._sanitize_filename(entity.name or entity.id)}.md",
        )

    async def _get_entity_relations(self, entity_id: str) -> list[Relation]:
        """Get all relations for an entity."""
        subgraph = await self._graph_store.get_neighbors(entity_id, depth=1)
        return subgraph.relations

    def _generate_wiki_links(self, entity_id: str, relations: list[Relation]) -> list[str]:
        """Generate [[entity-name|Display Name]] syntax."""
        links: list[str] = []
        graph = getattr(self._graph_store, "_graph", None)
        if graph is None:
            return links

        seen: set[str] = set()
        for rel in relations:
            for target_id in (rel.source_entity_id, rel.target_entity_id):
                if target_id == entity_id or target_id in seen:
                    continue
                seen.add(target_id)
                node_data = graph.nodes.get(target_id, {})
                name = node_data.get("name", target_id)
                filename = self._sanitize_filename(name)
                links.append(f"[[{filename}|{name}]]")

        return links

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Convert entity name to lowercase-kebab-case filename."""
        name = name.lower().strip()
        name = re.sub(r"[^\w\s-]", "", name)
        name = re.sub(r"[\s_]+", "-", name)
        name = re.sub(r"-{2,}", "-", name)
        return name[:80].rstrip("-")

    def _resolve_template(self, entity_type: str) -> Path:
        """Resolve template: entity_type.md → fallback entity.md."""
        specific = self._config.templates_dir / f"{entity_type.lower()}.md"
        if specific.exists():
            return specific
        return self._config.templates_dir / "entity.md"


# =========================================================================
# ForwardSyncService — Graph → Wiki (REQ-2)
# =========================================================================


class ForwardSyncService:
    """Syncs GraphStore entities to wiki pages."""

    def __init__(
        self,
        graph_store: BaseGraphStore,
        exporter: WikiExporter,
    ) -> None:
        self._graph_store = graph_store
        self._exporter = exporter

    async def sync_entity(self, entity_id: str) -> Path | None:
        """Sync single entity: read graph → build page → export."""
        entity = await self._graph_store.get_entity(entity_id)
        if entity is None:
            logger.warning("[FWD-SYNC] Entity not found: %s", entity_id)
            return None
        return await self._exporter.export_entity(entity_id)

    async def sync_since(self, since: datetime) -> ExportResult:
        """Catch-up sync for entities updated after timestamp."""
        graph = getattr(self._graph_store, "_graph", None)
        if graph is None:
            return ExportResult(errors=[{"reason": "graph_store_unavailable"}])

        entity_ids = []
        for nid, data in graph.nodes(data=True):
            if data.get("node_type") == "COMMUNITY":
                continue
            updated = data.get("updated_at")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated) if isinstance(updated, str) else updated
                    if updated_dt > since:
                        entity_ids.append(nid)
                except (ValueError, TypeError):
                    pass
            else:
                entity_ids.append(nid)

        if not entity_ids:
            return ExportResult(total_entities=0)

        return await self._exporter.export_batch(entity_ids)

    def _build_frontmatter(self, entity: Entity, relations: list[Relation]) -> dict[str, Any]:
        """Build frontmatter dict for entity page."""
        return {
            "entity_id": entity.id,
            "entity_type": entity.entity_type,
            "source_graph": "lightrag_v38",
            "source_document_id": entity.source_document_id,
            "confidence": entity.confidence,
            "relation_count": len(relations),
            "generated_at": datetime.now().isoformat(),
        }

    def _format_page_content(
        self,
        entity: Entity,
        relations: list[Relation],
        communities: list[str],
    ) -> str:
        """Format markdown content sections."""
        sections = []

        desc = entity.properties.get("description", entity.name)
        sections.append(f"## Description\n\n{desc}\n")

        props = {k: v for k, v in entity.properties.items() if k != "description" and v}
        if props:
            prop_lines = "\n".join(f"- **{k}**: {v}" for k, v in props.items())
            sections.append(f"## Properties\n\n{prop_lines}\n")

        if relations:
            link_lines = []
            for rel in relations[:50]:
                target = rel.target_entity_id if rel.source_entity_id == entity.id else rel.source_entity_id
                link_lines.append(f"- [[{target}]] ({rel.relation_type})")
            sections.append("## Related Entities\n\n" + "\n".join(link_lines) + "\n")

        if communities:
            comm_lines = "\n".join(f"- [[{c}]]" for c in communities)
            sections.append(f"## Communities\n\n{comm_lines}\n")

        return "\n".join(sections)


# =========================================================================
# IncrementalWikiSync — event-driven (REQ-3)
# =========================================================================


class IncrementalWikiSync:
    """Subscribes to IncrementalGraphUpdater events for incremental wiki sync."""

    _BACKOFF_DELAYS = [1.0, 5.0, 30.0]

    def __init__(
        self,
        forward_sync: ForwardSyncService,
        exporter: WikiExporter,
        max_retries: int = 3,
        retry_delay_s: float = 1.0,
        failed_events_path: Path | None = None,
    ) -> None:
        self._forward_sync = forward_sync
        self._exporter = exporter
        self._max_retries = max_retries
        self._retry_delay_s = retry_delay_s
        self._failed_events_path = failed_events_path or Path("docs/wiki/_failed_events.jsonl")
        self._running = False

    async def start(self) -> None:
        """Start listening for graph events."""
        self._running = True
        logger.info("[INC-SYNC] Started incremental wiki sync")

    async def stop(self) -> None:
        """Stop listening."""
        self._running = False
        logger.info("[INC-SYNC] Stopped incremental wiki sync")

    async def handle_event(self, event: GraphChangeEvent) -> None:
        """Handle a graph change event."""
        if not self._running:
            return

        if _metrics:
            _metrics.counter("wiki_sync_events_total")

        if not self._should_sync(event):
            return

        if event.event_type in (GraphEventType.ENTITY_CREATED, GraphEventType.ENTITY_UPDATED):
            await self._sync_with_retry(event.entity_id)
        elif event.event_type == GraphEventType.ENTITY_DELETED:
            await self._delete_wiki_page(event.entity_id)
        elif event.event_type in (GraphEventType.RELATION_ADDED, GraphEventType.RELATION_REMOVED):
            for eid in event.affected_entity_ids:
                await self._sync_with_retry(eid)
        elif event.event_type == GraphEventType.COMMUNITY_MERGED:
            for eid in event.affected_entity_ids:
                await self._sync_with_retry(eid)

    async def _sync_with_retry(self, entity_id: str) -> None:
        """Sync entity with retry logic."""
        for attempt in range(self._max_retries):
            try:
                await self._forward_sync.sync_entity(entity_id)
                return
            except Exception as exc:
                logger.warning(
                    "[INC-SYNC] Retry %d/%d for %s: %s",
                    attempt + 1, self._max_retries, entity_id, exc,
                )
                if attempt < self._max_retries - 1:
                    delay = self._BACKOFF_DELAYS[min(attempt, len(self._BACKOFF_DELAYS) - 1)]
                    await asyncio.sleep(delay)

        logger.error("[INC-SYNC] Failed after %d retries: %s", self._max_retries, entity_id)
        if _metrics:
            _metrics.counter("wiki_sync_failures_total")
        await self._write_failed_event(entity_id, "retry_exhausted")

    async def _delete_wiki_page(self, entity_id: str) -> None:
        """Delete wiki page for removed entity."""
        filename = self._exporter._sanitize_filename(entity_id)
        path = self._exporter._config.output_dir / f"{filename}.md"
        if path.exists():
            path.unlink()
            logger.info("[INC-SYNC] Deleted wiki page: %s", path)

    def _should_sync(self, event: GraphChangeEvent) -> bool:
        """Filter noisy events (embedding-only updates)."""
        meta = event.metadata or {}
        return meta.get("change_type") != "embedding_only"

    async def _write_failed_event(self, entity_id: str, reason: str) -> None:
        """Write to dead letter queue."""
        self._failed_events_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "entity_id": entity_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
        }
        async with self._exporter._lock:
            with open(self._failed_events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# =========================================================================
# ReverseSyncService — Wiki → Graph (REQ-4)
# =========================================================================


class ReverseSyncService:
    """Watches wiki entities dir for changes and syncs back to GraphStore."""

    def __init__(
        self,
        graph_store: BaseGraphStore,
        change_detector: Any = None,
        wiki_dir: Path = Path("docs/wiki/entities"),
        debounce_s: float = 2.0,
    ) -> None:
        self._graph_store = graph_store
        self._change_detector = change_detector
        self._wiki_dir = wiki_dir
        self._debounce_s = debounce_s
        self._observer: Any = None
        self._last_processed: dict[str, float] = {}

    async def start_watching(self) -> None:
        """Start watchdog observer on wiki_dir."""
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            service = self

            class WikiHandler(FileSystemEventHandler):
                def on_modified(self, event: Any) -> None:
                    if event.src_path.endswith(".md"):
                        try:
                            loop = asyncio.get_event_loop()
                            loop.create_task(service._on_file_event(event.src_path, "modified"))
                        except RuntimeError:
                            pass

                def on_created(self, event: Any) -> None:
                    if event.src_path.endswith(".md"):
                        try:
                            loop = asyncio.get_event_loop()
                            loop.create_task(service._on_file_event(event.src_path, "created"))
                        except RuntimeError:
                            pass

                def on_deleted(self, event: Any) -> None:
                    if event.src_path.endswith(".md"):
                        try:
                            loop = asyncio.get_event_loop()
                            loop.create_task(service._on_file_event(event.src_path, "deleted"))
                        except RuntimeError:
                            pass

            self._observer = Observer()
            self._observer.schedule(WikiHandler(), str(self._wiki_dir), recursive=False)
            self._observer.start()
            logger.info("[REV-SYNC] Watching %s", self._wiki_dir)
        except ImportError:
            logger.warning("[REV-SYNC] watchdog not installed, reverse sync disabled")

    async def stop_watching(self) -> None:
        """Stop watchdog observer."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            logger.info("[REV-SYNC] Stopped watching")

    async def handle_page_change(self, change: WikiPageChange) -> None:
        """Process wiki page change → update GraphStore."""
        if change.change_type == "deleted":
            logger.info("[REV-SYNC] Wiki page deleted: %s", change.entity_id)
            return

        new_relations = self._links_to_relations(change.added_links, change.entity_id)
        for rel_data in new_relations:
            try:
                relation = Relation(
                    id=f"wiki:{change.entity_id}:{rel_data['target']}",
                    source_entity_id=change.entity_id,
                    target_entity_id=rel_data["target"],
                    relation_type="related_to",
                    properties={"source": "wiki_edit"},
                )
                await self._graph_store.add_relation(relation)
                logger.info("[REV-SYNC] Added relation: %s → %s", change.entity_id, rel_data["target"])
            except Exception as exc:
                logger.warning("[REV-SYNC] Failed to add relation: %s", exc)

    def _parse_wiki_page(self, path: Path) -> WikiPageChange:
        """Parse markdown wiki page → WikiPageChange."""
        content = path.read_text(encoding="utf-8")
        entity_id = path.stem

        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        frontmatter: dict[str, Any] = {}
        body = content

        if fm_match:
            import yaml
            try:
                frontmatter = yaml.safe_load(fm_match.group(1)) or {}
            except Exception as exc:
                raise WikiParseError(f"Invalid frontmatter in {path}: {exc}") from exc
            body = content[fm_match.end():]

        links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", body)

        return WikiPageChange(
            entity_id=entity_id,
            page_path=path,
            change_type="modified",
            frontmatter=frontmatter,
            added_links=links,
        )

    def _links_to_relations(
        self, links: list[str], source_entity_id: str
    ) -> list[dict[str, str]]:
        """Convert [[target-id|Display]] → relation dicts."""
        return [
            {"source": source_entity_id, "target": link, "type": "related_to"}
            for link in links
        ]

    async def _on_file_event(self, path: str, change_type: str) -> None:
        """Handle filesystem event with debounce."""
        now = time.monotonic()
        last = self._last_processed.get(path, 0)
        if now - last < self._debounce_s:
            return
        self._last_processed[path] = now

        file_path = Path(path)
        if change_type == "deleted":
            change = WikiPageChange(
                entity_id=file_path.stem,
                page_path=file_path,
                change_type="deleted",
                frontmatter={},
            )
        else:
            try:
                change = self._parse_wiki_page(file_path)
            except WikiParseError as exc:
                logger.error("[REV-SYNC] Parse error: %s", exc)
                return

        await self.handle_page_change(change)


class WikiParseError(Exception):
    """Error parsing wiki page frontmatter or content."""


# =========================================================================
# WikiSearchIndexer — HybridSearchService integration (REQ-6)
# =========================================================================


class WikiSearchIndexer:
    """Indexes wiki pages through existing HybridSearchService."""

    def __init__(
        self,
        hybrid_search: Any,
        wiki_dir: Path = Path("docs/wiki/entities"),
    ) -> None:
        self._hybrid_search = hybrid_search
        self._wiki_dir = wiki_dir

    async def index_page(self, page_path: Path) -> None:
        """Extract text (excluding frontmatter), index via hybrid_search."""
        text = self._extract_searchable_text(page_path)
        if not text.strip():
            logger.warning("[WIKI-IDX] Empty content, skipping: %s", page_path)
            return

        entity_id = page_path.stem
        await self._hybrid_search.index_document(
            doc_id=entity_id,
            content=text,
            metadata={"source": "wiki", "path": str(page_path)},
        )

    async def index_all_pages(self) -> int:
        """Index all wiki pages. Returns count."""
        if not self._wiki_dir.exists():
            return 0

        count = 0
        for page_path in self._wiki_dir.glob("*.md"):
            try:
                await self.index_page(page_path)
                count += 1
            except Exception as exc:
                logger.warning("[WIKI-IDX] Failed to index %s: %s", page_path, exc)
        return count

    async def remove_page(self, entity_id: str) -> None:
        """Remove doc from hybrid search index."""
        await self._hybrid_search.remove_document(entity_id)

    def _extract_searchable_text(self, page_path: Path) -> str:
        """Strip YAML frontmatter, resolve wiki-links to display text."""
        content = page_path.read_text(encoding="utf-8")
        content = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL)
        content = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", content)
        content = re.sub(r"\[\[([^\]]+)\]\]", r"\1", content)
        return content.strip()
