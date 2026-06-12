"""
Link Registry — Cross-System Entity Links.

Provides typed links between entities across different memory subsystems.
Supports graph traversal, strength-based filtering, and batch operations.
SQLite-backed with audit trail.

Migrated from D:\\1C-Enterprise_Framework\\memory-orchestrator\\src\\link_registry.py
"""

import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class LinkType(str, Enum):
    """Types of relationships between entities.

    ADR-L1 (roadmap 260612 LinkRegistry): типология = только типы с писателем
    или ручной семантикой. Авто-писатели: MIRRORS (cross_store_sync),
    DERIVES_FROM (reflection), SESSION_CONTEXT (route_and_save multi-target),
    PROMOTED_TO (WikiPromoter). Ручной словарь create_link: SUPPORTS,
    CONTRADICTS, EXTENDS, SUPERSEDED_BY. Ретированы 2026-06-12: BASED_ON
    («pattern based on documentation» — non-goal по ADR-D2/D4 260612 pdf-docs,
    docs-рёбра недостижимы; 0 рёбер за всю историю) и GRAPH_NODE (ни писателя,
    ни читателя, ни семантики; 0 рёбер).
    """

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    DERIVES_FROM = "derives_from"
    SESSION_CONTEXT = "session_context"
    PROMOTED_TO = "promoted_to"
    SUPERSEDED_BY = "superseded_by"
    MIRRORS = "mirrors"

    @property
    def description(self) -> str:
        """Human-readable description of the link type."""
        descriptions = {
            LinkType.SUPPORTS: "Source entity supports or reinforces target",
            LinkType.CONTRADICTS: "Source entity contradicts or conflicts with target",
            LinkType.EXTENDS: "Source entity extends or augments target",
            LinkType.DERIVES_FROM: "Source entity derives its content from target",
            LinkType.SESSION_CONTEXT: "Entities are linked through a shared session context",
            LinkType.PROMOTED_TO: "Source entity has been promoted to wiki page (target)",
            LinkType.SUPERSEDED_BY: "Source entity is superseded by a newer version (target)",
            LinkType.MIRRORS: "Source entity mirrors content from target",
        }
        return descriptions.get(self, "")

    @classmethod
    def from_string(cls, value: str) -> "LinkType":
        value_lower = value.lower()
        for member in cls:
            if member.value == value_lower:
                return member
        raise ValueError(f"Unknown link type: {value}")


@dataclass
class EntityLink:
    """Link between two entities in the unified namespace."""

    link_id: str
    source_id: str
    target_id: str
    link_type: LinkType
    strength: float
    created_at: datetime = field(default_factory=datetime.now)
    created_by: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = False
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.strength <= 1.0:
            raise ValueError(f"Strength must be between 0.0 and 1.0, got {self.strength}")
        if not self.source_id or not self.target_id:
            raise ValueError("source_id and target_id are required")
        if self.source_id == self.target_id:
            raise ValueError("Cannot create self-referencing link")
        if isinstance(self.link_type, str):
            self.link_type = LinkType.from_string(self.link_type)
        if self.metadata is None:
            self.metadata = {}

    def __str__(self) -> str:
        return (
            f"{self.source_id} --[{self.link_type.value}:{self.strength:.2f}]--> {self.target_id}"
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EntityLink):
            return self.link_id == other.link_id
        return False

    def __hash__(self) -> int:
        return hash(self.link_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "link_type": self.link_type.value,
            "strength": self.strength,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
            "bidirectional": self.bidirectional,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntityLink":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        expires_at = data.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        return cls(
            link_id=data["link_id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            link_type=LinkType.from_string(data["link_type"]),
            strength=float(data["strength"]),
            created_at=created_at or datetime.now(),
            created_by=data.get("created_by", "system"),
            metadata=data.get("metadata", {}),
            bidirectional=data.get("bidirectional", False),
            expires_at=expires_at,
        )

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "EntityLink":
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        created_at = (
            datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
        )
        expires_at = datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None
        return cls(
            link_id=row["link_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            link_type=LinkType.from_string(row["link_type"]),
            strength=row["strength"],
            created_at=created_at,
            created_by=row["created_by"],
            metadata=metadata,
            bidirectional=bool(row["bidirectional"]),
            expires_at=expires_at,
        )

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


@dataclass
class RelatedEntity:
    """Result of graph traversal query."""

    entity_id: str
    link_path: list[str]
    total_strength: float
    depth: int
    link_types: list[str]

    @property
    def effective_strength(self) -> float:
        decay = 0.9 ** (self.depth - 1) if self.depth > 0 else 1.0
        return self.total_strength * decay

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "link_path": self.link_path,
            "total_strength": self.total_strength,
            "effective_strength": self.effective_strength,
            "depth": self.depth,
            "link_types": self.link_types,
        }


class LinkRegistry:
    """Registry for managing cross-system entity links with SQLite backend."""

    SCHEMA_VERSION = 1

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            # Env override (roadmap 260609 P0.2): lets tests redirect the
            # default registry away from the production data/link_registry.db.
            db_path = os.environ.get("LINK_REGISTRY_PATH")
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "link_registry.db")
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity_links (
                    link_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    link_type TEXT NOT NULL,
                    strength REAL NOT NULL DEFAULT 0.8,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL DEFAULT 'system',
                    metadata TEXT,
                    bidirectional INTEGER DEFAULT 0,
                    expires_at TEXT,
                    CHECK (strength >= 0.0 AND strength <= 1.0),
                    -- ADR-L1 2026-06-12: based_on/graph_node ретированы (свежие БД;
                    -- существующие БД хранят старый CHECK — он шире, безвреден)
                    CHECK (link_type IN (
                        'supports', 'contradicts',
                        'extends', 'derives_from', 'session_context',
                        'promoted_to', 'superseded_by', 'mirrors'
                    ))
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON entity_links(source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON entity_links(target_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_type ON entity_links(link_type)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_strength ON entity_links(strength)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_source_type ON entity_links(source_id, link_type)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_target_type ON entity_links(target_id, link_type)"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS link_history (
                    history_id TEXT PRIMARY KEY,
                    link_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    old_strength REAL,
                    new_strength REAL,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT NOT NULL,
                    reason TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_link ON link_history(link_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_history_action ON link_history(action)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_links_created ON entity_links(created_at)"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS link_stats (
                    entity_id TEXT PRIMARY KEY,
                    outgoing_count INTEGER DEFAULT 0,
                    incoming_count INTEGER DEFAULT 0,
                    avg_strength REAL DEFAULT 0.0,
                    last_updated TEXT NOT NULL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_info (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            cursor.execute(
                "INSERT OR REPLACE INTO schema_info (key, value) VALUES (?, ?)",
                ("version", str(self.SCHEMA_VERSION)),
            )
            conn.commit()

    # === CRUD ===

    @staticmethod
    def _trace(event: str, **fields: Any) -> None:
        """P3.1 (roadmap 260612 LinkRegistry): жизнь рёбер в §27 observability.

        Fail-soft + lazy import: link_registry импортируется хуками — тяжёлых
        зависимостей на module-level быть не должно; отказ лога не ломает CRUD.
        Opt-out: MEMORY_LINKS_LOG_DISABLE=1.
        """
        try:
            from ..infrastructure.trace_log import write_trace

            write_trace(
                "memory-links.log", event, disable_env="MEMORY_LINKS_LOG_DISABLE", **fields
            )
        except Exception:
            pass

    @staticmethod
    def _validate_entity_id(entity_id: str, arg_name: str) -> None:
        """P0.1 (roadmap 260612 LinkRegistry): рёбра только на unified-ID.

        Структурная проверка `type:source:identifier` (3 непустые части) —
        без привязки к enum'ам (будущие source'ы не ломают вход), но сырые
        UUID и пустые строки отклоняются. Исторические 3 raw-UUID ребра
        были слепыми для TTL-cascade/BFS — вход теперь защищён.
        """
        parts = entity_id.split(":", 2)
        if len(parts) != 3 or not all(p.strip() for p in parts):
            raise ValueError(
                f"{arg_name} must be a unified ID 'type:source:identifier', "
                f"got {entity_id!r} (raw UUIDs are rejected — roadmap 260612 P0.1)"
            )

    def create_link(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType,
        strength: float = 0.8,
        metadata: dict[str, Any] | None = None,
        created_by: str = "system",
        bidirectional: bool = False,
        expires_at: datetime | None = None,
    ) -> EntityLink:
        self._validate_entity_id(source_id, "source_id")
        self._validate_entity_id(target_id, "target_id")
        link_id = str(uuid4())
        link = EntityLink(
            link_id=link_id,
            source_id=source_id,
            target_id=target_id,
            link_type=link_type,
            strength=strength,
            created_at=datetime.now(),
            created_by=created_by,
            metadata=metadata or {},
            bidirectional=bidirectional,
            expires_at=expires_at,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT link_id FROM entity_links WHERE source_id = ? AND target_id = ? AND link_type = ?",
                (source_id, target_id, link_type.value),
            )
            if cursor.fetchone():
                raise ValueError(
                    f"Link already exists: {source_id} --[{link_type.value}]--> {target_id}"
                )

            cursor.execute(
                """
                INSERT INTO entity_links
                (link_id, source_id, target_id, link_type, strength, created_at,
                 created_by, metadata, bidirectional, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    link.link_id,
                    link.source_id,
                    link.target_id,
                    link.link_type.value,
                    link.strength,
                    link.created_at.isoformat(),
                    link.created_by,
                    json.dumps(link.metadata),
                    1 if link.bidirectional else 0,
                    link.expires_at.isoformat() if link.expires_at else None,
                ),
            )

            cursor.execute(
                """
                INSERT INTO link_history
                (history_id, link_id, action, new_strength, changed_at, changed_by, reason)
                VALUES (?, ?, 'create', ?, ?, ?, ?)
            """,
                (
                    str(uuid4()),
                    link.link_id,
                    link.strength,
                    datetime.now().isoformat(),
                    created_by,
                    "Link created",
                ),
            )

            self._update_stats(cursor, source_id)
            self._update_stats(cursor, target_id)
            conn.commit()

        self._trace(
            "link_create",
            link_id=link.link_id,
            link_type=link_type.value,
            source_id=source_id,
            target_id=target_id,
            created_by=created_by,
        )
        return link

    def get_link(self, link_id: str) -> EntityLink | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entity_links WHERE link_id = ?", (link_id,))
            row = cursor.fetchone()
            return EntityLink.from_row(row) if row else None

    def update_link(
        self,
        link_id: str,
        strength: float | None = None,
        metadata: dict[str, Any] | None = None,
        updated_by: str = "system",
        reason: str = "",
    ) -> bool:
        link = self.get_link(link_id)
        if not link:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params: list[Any] = []

            if strength is not None:
                if not 0.0 <= strength <= 1.0:
                    raise ValueError(f"Strength must be between 0.0 and 1.0, got {strength}")
                cursor.execute(
                    """
                    INSERT INTO link_history
                    (history_id, link_id, action, old_strength, new_strength, changed_at, changed_by, reason)
                    VALUES (?, ?, 'update', ?, ?, ?, ?, ?)
                """,
                    (
                        str(uuid4()),
                        link_id,
                        link.strength,
                        strength,
                        datetime.now().isoformat(),
                        updated_by,
                        reason,
                    ),
                )
                updates.append("strength = ?")
                params.append(strength)

            if metadata is not None:
                merged = {**link.metadata, **metadata}
                updates.append("metadata = ?")
                params.append(json.dumps(merged))

            if not updates:
                return True

            params.append(link_id)
            cursor.execute(
                f"UPDATE entity_links SET {', '.join(updates)} WHERE link_id = ?", params
            )
            self._update_stats(cursor, link.source_id)
            self._update_stats(cursor, link.target_id)
            conn.commit()

        return True

    def delete_link(self, link_id: str, deleted_by: str = "system") -> bool:
        link = self.get_link(link_id)
        if not link:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO link_history
                (history_id, link_id, action, old_strength, changed_at, changed_by, reason)
                VALUES (?, ?, 'delete', ?, ?, ?, ?)
            """,
                (
                    str(uuid4()),
                    link_id,
                    link.strength,
                    datetime.now().isoformat(),
                    deleted_by,
                    "Link deleted",
                ),
            )
            cursor.execute("DELETE FROM entity_links WHERE link_id = ?", (link_id,))
            self._update_stats(cursor, link.source_id)
            self._update_stats(cursor, link.target_id)
            conn.commit()

        return True

    # === Query ===

    def get_links_from(
        self,
        entity_id: str,
        link_types: list[LinkType] | None = None,
        min_strength: float = 0.0,
    ) -> list[EntityLink]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM entity_links WHERE source_id = ? AND strength >= ?"
            params: list[Any] = [entity_id, min_strength]
            if link_types:
                placeholders = ",".join("?" * len(link_types))
                query += f" AND link_type IN ({placeholders})"
                params.extend([lt.value for lt in link_types])
            query += " ORDER BY strength DESC"
            cursor.execute(query, params)
            return [EntityLink.from_row(row) for row in cursor.fetchall()]

    def get_links_to(
        self,
        entity_id: str,
        link_types: list[LinkType] | None = None,
        min_strength: float = 0.0,
    ) -> list[EntityLink]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM entity_links WHERE target_id = ? AND strength >= ?"
            params: list[Any] = [entity_id, min_strength]
            if link_types:
                placeholders = ",".join("?" * len(link_types))
                query += f" AND link_type IN ({placeholders})"
                params.extend([lt.value for lt in link_types])
            query += " ORDER BY strength DESC"
            cursor.execute(query, params)
            return [EntityLink.from_row(row) for row in cursor.fetchall()]

    def get_all_links(
        self,
        entity_id: str,
        link_types: list[LinkType] | None = None,
        min_strength: float = 0.0,
    ) -> dict[str, list[EntityLink]]:
        return {
            "outgoing": self.get_links_from(entity_id, link_types, min_strength),
            "incoming": self.get_links_to(entity_id, link_types, min_strength),
        }

    def find_link(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType | None = None,
    ) -> EntityLink | None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if link_type:
                cursor.execute(
                    "SELECT * FROM entity_links WHERE source_id = ? AND target_id = ? AND link_type = ?",
                    (source_id, target_id, link_type.value),
                )
            else:
                cursor.execute(
                    "SELECT * FROM entity_links WHERE source_id = ? AND target_id = ?",
                    (source_id, target_id),
                )
            row = cursor.fetchone()
            return EntityLink.from_row(row) if row else None

    # === Graph Traversal ===

    def get_related_entities(
        self,
        entity_id: str,
        link_types: list[LinkType] | None = None,
        min_strength: float = 0.5,
        max_depth: int = 2,
        direction: str = "both",
    ) -> list[RelatedEntity]:
        visited = {entity_id}
        queue: list[tuple[str, list[str], list[str], float, int]] = [(entity_id, [], [], 1.0, 0)]
        results: list[RelatedEntity] = []

        while queue:
            current_id, path, types, cumulative_strength, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            links: list[EntityLink] = []
            if direction in ("outgoing", "both"):
                links.extend(self.get_links_from(current_id, link_types, min_strength))
            if direction in ("incoming", "both"):
                links.extend(self.get_links_to(current_id, link_types, min_strength))

            for link in links:
                related_id = link.target_id if link.source_id == current_id else link.source_id
                if related_id not in visited:
                    visited.add(related_id)
                    new_path = path + [link.link_id]
                    new_types = types + [link.link_type.value]
                    new_strength = cumulative_strength * link.strength

                    results.append(
                        RelatedEntity(
                            entity_id=related_id,
                            link_path=new_path,
                            total_strength=new_strength,
                            depth=depth + 1,
                            link_types=new_types,
                        )
                    )
                    queue.append((related_id, new_path, new_types, new_strength, depth + 1))

        return sorted(results, key=lambda r: r.effective_strength, reverse=True)

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> list[EntityLink] | None:
        if source_id == target_id:
            return []
        visited = {source_id}
        queue: list[tuple[str, list[str]]] = [(source_id, [])]

        while queue:
            current_id, path = queue.pop(0)
            if len(path) >= max_depth:
                continue
            for link in self.get_links_from(current_id):
                if link.target_id == target_id:
                    full_path = path + [link.link_id]
                    result: list[EntityLink] = []
                    for lid in full_path:
                        found = self.get_link(lid)
                        if found is not None:
                            result.append(found)
                    return result if result else None
                if link.target_id not in visited:
                    visited.add(link.target_id)
                    queue.append((link.target_id, path + [link.link_id]))

        return None

    # === Bulk ===

    def create_links_batch(
        self,
        links: list[tuple[str, str, LinkType, float]],
        created_by: str = "system",
    ) -> list[EntityLink]:
        created = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for source_id, target_id, link_type, strength in links:
                self._validate_entity_id(source_id, "source_id")
                self._validate_entity_id(target_id, "target_id")
                try:
                    link_id = str(uuid4())
                    now = datetime.now().isoformat()
                    cursor.execute(
                        """
                        INSERT INTO entity_links
                        (link_id, source_id, target_id, link_type, strength, created_at, created_by, metadata, bidirectional)
                        VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 0)
                    """,
                        (link_id, source_id, target_id, link_type.value, strength, now, created_by),
                    )
                    # P0.3: batch-путь раньше не журналировал create — history
                    # обязан быть полным независимо от входа.
                    cursor.execute(
                        """
                        INSERT INTO link_history
                        (history_id, link_id, action, new_strength, changed_at, changed_by, reason)
                        VALUES (?, ?, 'create', ?, ?, ?, 'Link created (batch)')
                    """,
                        (str(uuid4()), link_id, strength, now, created_by),
                    )
                    self._update_stats(cursor, source_id)
                    self._update_stats(cursor, target_id)
                    created.append(
                        EntityLink(
                            link_id=link_id,
                            source_id=source_id,
                            target_id=target_id,
                            link_type=link_type,
                            strength=strength,
                            created_at=datetime.fromisoformat(now),
                            created_by=created_by,
                        )
                    )
                except sqlite3.IntegrityError:
                    continue
            conn.commit()
        if created:
            self._trace("link_create", size=len(created), created_by=created_by, reason="batch")
        return created

    def delete_links_for_entity(
        self, entity_id: str, changed_by: str = "system", reason: str = "entity removed"
    ) -> int:
        """Delete all edges touching entity_id.

        P0.3 (roadmap 260612 LinkRegistry): удаления журналируются в
        link_history (раньше 29 из 61 созданных рёбер исчезли бесследно) и
        stats затронутых соседей пересчитываются (раньше link_stats копил
        orphan-строки — 73 сущности при 32 рёбрах).
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT link_id, source_id, target_id, strength FROM entity_links "
                "WHERE source_id = ? OR target_id = ?",
                (entity_id, entity_id),
            )
            doomed = cursor.fetchall()
            if not doomed:
                return 0

            now = datetime.now().isoformat()
            endpoints: set[str] = set()
            for row in doomed:
                cursor.execute(
                    """
                    INSERT INTO link_history
                    (history_id, link_id, action, old_strength, changed_at, changed_by, reason)
                    VALUES (?, ?, 'delete', ?, ?, ?, ?)
                """,
                    (str(uuid4()), row["link_id"], row["strength"], now, changed_by, reason),
                )
                endpoints.add(row["source_id"])
                endpoints.add(row["target_id"])

            cursor.execute(
                "DELETE FROM entity_links WHERE source_id = ? OR target_id = ?",
                (entity_id, entity_id),
            )
            deleted = cursor.rowcount
            for ep in endpoints:
                self._update_stats(cursor, ep)
            conn.commit()
        self._trace(
            "link_delete",
            source_id=entity_id,
            size=int(deleted),
            created_by=changed_by,
            reason=reason,
        )
        return int(deleted)

    # === Stats ===

    def _update_stats(self, cursor: sqlite3.Cursor, entity_id: str) -> None:
        cursor.execute(
            """
            INSERT OR REPLACE INTO link_stats (entity_id, outgoing_count, incoming_count, avg_strength, last_updated)
            SELECT ?,
                (SELECT COUNT(*) FROM entity_links WHERE source_id = ?),
                (SELECT COUNT(*) FROM entity_links WHERE target_id = ?),
                (SELECT COALESCE(AVG(strength), 0) FROM entity_links WHERE source_id = ? OR target_id = ?),
                ?
        """,
            (entity_id, entity_id, entity_id, entity_id, entity_id, datetime.now().isoformat()),
        )
        # P0.2: сущность без рёбер не должна жить в stats (orphan-строки —
        # источник рассинхрона 73-сущности-при-32-рёбрах).
        cursor.execute(
            "DELETE FROM link_stats WHERE entity_id = ? "
            "AND outgoing_count = 0 AND incoming_count = 0",
            (entity_id,),
        )

    def rebuild_stats(self) -> dict[str, int]:
        """P0.2 (roadmap 260612 LinkRegistry): полный idempotent-пересчёт
        link_stats из entity_links — лечит исторический рассинхрон и
        вызывается из maintenance-каденса.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM link_stats")
            removed = cursor.rowcount
            cursor.execute(
                """
                INSERT INTO link_stats (entity_id, outgoing_count, incoming_count, avg_strength, last_updated)
                SELECT e.entity_id,
                    (SELECT COUNT(*) FROM entity_links WHERE source_id = e.entity_id),
                    (SELECT COUNT(*) FROM entity_links WHERE target_id = e.entity_id),
                    (SELECT COALESCE(AVG(strength), 0) FROM entity_links
                     WHERE source_id = e.entity_id OR target_id = e.entity_id),
                    ?
                FROM (
                    SELECT source_id AS entity_id FROM entity_links
                    UNION SELECT target_id FROM entity_links
                ) e
            """,
                (datetime.now().isoformat(),),
            )
            rebuilt = cursor.rowcount
            conn.commit()
        return {"removed": int(removed), "rebuilt": int(rebuilt)}

    def get_entity_stats(self, entity_id: str) -> dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM link_stats WHERE entity_id = ?", (entity_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                "entity_id": entity_id,
                "outgoing_count": 0,
                "incoming_count": 0,
                "avg_strength": 0.0,
            }

    def get_registry_stats(self) -> dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM entity_links")
            total = cursor.fetchone()["count"]
            cursor.execute("""
                SELECT link_type, COUNT(*) as count, AVG(strength) as avg_strength
                FROM entity_links GROUP BY link_type
            """)
            by_type = {
                row["link_type"]: {"count": row["count"], "avg_strength": row["avg_strength"]}
                for row in cursor.fetchall()
            }
            cursor.execute("""
                SELECT COUNT(DISTINCT entity_id) as count FROM (
                    SELECT source_id as entity_id FROM entity_links
                    UNION SELECT target_id as entity_id FROM entity_links
                )
            """)
            unique_entities = cursor.fetchone()["count"]
            avg_links = total / unique_entities if unique_entities > 0 else 0.0
            cursor.execute("SELECT AVG(strength) as avg FROM entity_links")
            row = cursor.fetchone()
            avg_strength = row["avg"] if row and row["avg"] is not None else 0.0
            return {
                "total_links": total,
                "unique_entities": unique_entities,
                "avg_links_per_entity": round(avg_links, 2),
                "avg_strength": round(avg_strength, 3),
                "by_type": by_type,
                "schema_version": self.SCHEMA_VERSION,
            }

    # === Maintenance ===

    def cleanup_expired(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM entity_links WHERE expires_at IS NOT NULL AND expires_at < ?",
                (datetime.now().isoformat(),),
            )
            deleted = cursor.rowcount
            conn.commit()
        return int(deleted)

    def vacuum(self) -> None:
        with self._get_connection() as conn:
            conn.execute("VACUUM")

    def export(self) -> dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entity_links")
            links = [EntityLink.from_row(row).to_dict() for row in cursor.fetchall()]
            return {
                "version": self.SCHEMA_VERSION,
                "exported_at": datetime.now().isoformat(),
                "links": links,
                "stats": self.get_registry_stats(),
            }

    def import_links(self, data: dict[str, Any], replace: bool = False) -> int:
        links_data = data.get("links", [])
        if not links_data:
            return 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if replace:
                cursor.execute("DELETE FROM entity_links")
            imported = 0
            for link_dict in links_data:
                try:
                    link = EntityLink.from_dict(link_dict)
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO entity_links
                        (link_id, source_id, target_id, link_type, strength, created_at,
                         created_by, metadata, bidirectional, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            link.link_id,
                            link.source_id,
                            link.target_id,
                            link.link_type.value,
                            link.strength,
                            link.created_at.isoformat(),
                            link.created_by,
                            json.dumps(link.metadata),
                            1 if link.bidirectional else 0,
                            link.expires_at.isoformat() if link.expires_at else None,
                        ),
                    )
                    if cursor.rowcount > 0:
                        imported += 1
                except Exception:
                    continue
            conn.commit()
        return imported

    def get_link_history(self, link_id: str) -> list[dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM link_history WHERE link_id = ? ORDER BY changed_at DESC", (link_id,)
            )
            return [dict(row) for row in cursor.fetchall()]


# Global registry instance
_global_registry: LinkRegistry | None = None


def get_link_registry() -> LinkRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = LinkRegistry()
    return _global_registry


def set_link_registry(registry: LinkRegistry) -> None:
    global _global_registry
    _global_registry = registry
