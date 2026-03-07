"""
Link Registry — Cross-System Entity Links.

Provides typed links between entities across different memory subsystems.
Supports graph traversal, strength-based filtering, and batch operations.
SQLite-backed with audit trail.

Migrated from D:\\1C-Enterprise_Framework\\memory-orchestrator\\src\\link_registry.py
"""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4


class LinkType(str, Enum):
    """Types of relationships between entities."""

    BASED_ON = "based_on"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    DERIVES_FROM = "derives_from"
    SESSION_CONTEXT = "session_context"

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
    metadata: Dict[str, Any] = field(default_factory=dict)
    bidirectional: bool = False
    expires_at: Optional[datetime] = None

    def __post_init__(self):
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
        return f"{self.source_id} --[{self.link_type.value}:{self.strength:.2f}]--> {self.target_id}"

    def __eq__(self, other) -> bool:
        if isinstance(other, EntityLink):
            return self.link_id == other.link_id
        return False

    def __hash__(self) -> int:
        return hash(self.link_id)

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "EntityLink":
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
        created_at = datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.now()
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
    link_path: List[str]
    total_strength: float
    depth: int
    link_types: List[str]

    @property
    def effective_strength(self) -> float:
        decay = 0.9 ** (self.depth - 1) if self.depth > 0 else 1.0
        return self.total_strength * decay

    def to_dict(self) -> Dict[str, Any]:
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

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(data_dir / "link_registry.db")
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
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
                    CHECK (link_type IN (
                        'based_on', 'supports', 'contradicts',
                        'extends', 'derives_from', 'session_context'
                    ))
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON entity_links(source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON entity_links(target_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_type ON entity_links(link_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_strength ON entity_links(strength)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_source_type ON entity_links(source_id, link_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_target_type ON entity_links(target_id, link_type)")

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

    def create_link(
        self,
        source_id: str,
        target_id: str,
        link_type: LinkType,
        strength: float = 0.8,
        metadata: Optional[Dict] = None,
        created_by: str = "system",
        bidirectional: bool = False,
        expires_at: Optional[datetime] = None,
    ) -> EntityLink:
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
                raise ValueError(f"Link already exists: {source_id} --[{link_type.value}]--> {target_id}")

            cursor.execute("""
                INSERT INTO entity_links
                (link_id, source_id, target_id, link_type, strength, created_at,
                 created_by, metadata, bidirectional, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                link.link_id, link.source_id, link.target_id,
                link.link_type.value, link.strength, link.created_at.isoformat(),
                link.created_by, json.dumps(link.metadata),
                1 if link.bidirectional else 0,
                link.expires_at.isoformat() if link.expires_at else None,
            ))

            cursor.execute("""
                INSERT INTO link_history
                (history_id, link_id, action, new_strength, changed_at, changed_by, reason)
                VALUES (?, ?, 'create', ?, ?, ?, ?)
            """, (str(uuid4()), link.link_id, link.strength, datetime.now().isoformat(), created_by, "Link created"))

            self._update_stats(cursor, source_id)
            self._update_stats(cursor, target_id)
            conn.commit()

        return link

    def get_link(self, link_id: str) -> Optional[EntityLink]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entity_links WHERE link_id = ?", (link_id,))
            row = cursor.fetchone()
            return EntityLink.from_row(row) if row else None

    def update_link(
        self,
        link_id: str,
        strength: Optional[float] = None,
        metadata: Optional[Dict] = None,
        updated_by: str = "system",
        reason: str = "",
    ) -> bool:
        link = self.get_link(link_id)
        if not link:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            updates = []
            params: list = []

            if strength is not None:
                if not 0.0 <= strength <= 1.0:
                    raise ValueError(f"Strength must be between 0.0 and 1.0, got {strength}")
                cursor.execute("""
                    INSERT INTO link_history
                    (history_id, link_id, action, old_strength, new_strength, changed_at, changed_by, reason)
                    VALUES (?, ?, 'update', ?, ?, ?, ?, ?)
                """, (str(uuid4()), link_id, link.strength, strength, datetime.now().isoformat(), updated_by, reason))
                updates.append("strength = ?")
                params.append(strength)

            if metadata is not None:
                merged = {**link.metadata, **metadata}
                updates.append("metadata = ?")
                params.append(json.dumps(merged))

            if not updates:
                return True

            params.append(link_id)
            cursor.execute(f"UPDATE entity_links SET {', '.join(updates)} WHERE link_id = ?", params)
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
            cursor.execute("""
                INSERT INTO link_history
                (history_id, link_id, action, old_strength, changed_at, changed_by, reason)
                VALUES (?, ?, 'delete', ?, ?, ?, ?)
            """, (str(uuid4()), link_id, link.strength, datetime.now().isoformat(), deleted_by, "Link deleted"))
            cursor.execute("DELETE FROM entity_links WHERE link_id = ?", (link_id,))
            self._update_stats(cursor, link.source_id)
            self._update_stats(cursor, link.target_id)
            conn.commit()

        return True

    # === Query ===

    def get_links_from(
        self, entity_id: str, link_types: Optional[List[LinkType]] = None, min_strength: float = 0.0,
    ) -> List[EntityLink]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM entity_links WHERE source_id = ? AND strength >= ?"
            params: list = [entity_id, min_strength]
            if link_types:
                placeholders = ",".join("?" * len(link_types))
                query += f" AND link_type IN ({placeholders})"
                params.extend([lt.value for lt in link_types])
            query += " ORDER BY strength DESC"
            cursor.execute(query, params)
            return [EntityLink.from_row(row) for row in cursor.fetchall()]

    def get_links_to(
        self, entity_id: str, link_types: Optional[List[LinkType]] = None, min_strength: float = 0.0,
    ) -> List[EntityLink]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM entity_links WHERE target_id = ? AND strength >= ?"
            params: list = [entity_id, min_strength]
            if link_types:
                placeholders = ",".join("?" * len(link_types))
                query += f" AND link_type IN ({placeholders})"
                params.extend([lt.value for lt in link_types])
            query += " ORDER BY strength DESC"
            cursor.execute(query, params)
            return [EntityLink.from_row(row) for row in cursor.fetchall()]

    def get_all_links(
        self, entity_id: str, link_types: Optional[List[LinkType]] = None, min_strength: float = 0.0,
    ) -> Dict[str, List[EntityLink]]:
        return {
            "outgoing": self.get_links_from(entity_id, link_types, min_strength),
            "incoming": self.get_links_to(entity_id, link_types, min_strength),
        }

    def find_link(
        self, source_id: str, target_id: str, link_type: Optional[LinkType] = None,
    ) -> Optional[EntityLink]:
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
        link_types: Optional[List[LinkType]] = None,
        min_strength: float = 0.5,
        max_depth: int = 2,
        direction: str = "both",
    ) -> List[RelatedEntity]:
        visited = {entity_id}
        queue: List[Tuple[str, List[str], List[str], float, int]] = [
            (entity_id, [], [], 1.0, 0)
        ]
        results: List[RelatedEntity] = []

        while queue:
            current_id, path, types, cumulative_strength, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            links: List[EntityLink] = []
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

                    results.append(RelatedEntity(
                        entity_id=related_id,
                        link_path=new_path,
                        total_strength=new_strength,
                        depth=depth + 1,
                        link_types=new_types,
                    ))
                    queue.append((related_id, new_path, new_types, new_strength, depth + 1))

        return sorted(results, key=lambda r: r.effective_strength, reverse=True)

    def find_path(
        self, source_id: str, target_id: str, max_depth: int = 5,
    ) -> Optional[List[EntityLink]]:
        if source_id == target_id:
            return []
        visited = {source_id}
        queue: List[Tuple[str, List[str]]] = [(source_id, [])]

        while queue:
            current_id, path = queue.pop(0)
            if len(path) >= max_depth:
                continue
            for link in self.get_links_from(current_id):
                if link.target_id == target_id:
                    full_path = path + [link.link_id]
                    return [self.get_link(lid) for lid in full_path if self.get_link(lid)]
                if link.target_id not in visited:
                    visited.add(link.target_id)
                    queue.append((link.target_id, path + [link.link_id]))

        return None

    # === Bulk ===

    def create_links_batch(
        self, links: List[Tuple[str, str, LinkType, float]], created_by: str = "system",
    ) -> List[EntityLink]:
        created = []
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for source_id, target_id, link_type, strength in links:
                try:
                    link_id = str(uuid4())
                    now = datetime.now().isoformat()
                    cursor.execute("""
                        INSERT INTO entity_links
                        (link_id, source_id, target_id, link_type, strength, created_at, created_by, metadata, bidirectional)
                        VALUES (?, ?, ?, ?, ?, ?, ?, '{}', 0)
                    """, (link_id, source_id, target_id, link_type.value, strength, now, created_by))
                    created.append(EntityLink(
                        link_id=link_id, source_id=source_id, target_id=target_id,
                        link_type=link_type, strength=strength,
                        created_at=datetime.fromisoformat(now), created_by=created_by,
                    ))
                except sqlite3.IntegrityError:
                    continue
            conn.commit()
        return created

    def delete_links_for_entity(self, entity_id: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM entity_links WHERE source_id = ? OR target_id = ?", (entity_id, entity_id))
            deleted = cursor.rowcount
            conn.commit()
        return deleted

    # === Stats ===

    def _update_stats(self, cursor: sqlite3.Cursor, entity_id: str):
        cursor.execute("""
            INSERT OR REPLACE INTO link_stats (entity_id, outgoing_count, incoming_count, avg_strength, last_updated)
            SELECT ?,
                (SELECT COUNT(*) FROM entity_links WHERE source_id = ?),
                (SELECT COUNT(*) FROM entity_links WHERE target_id = ?),
                (SELECT COALESCE(AVG(strength), 0) FROM entity_links WHERE source_id = ? OR target_id = ?),
                ?
        """, (entity_id, entity_id, entity_id, entity_id, entity_id, datetime.now().isoformat()))

    def get_entity_stats(self, entity_id: str) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM link_stats WHERE entity_id = ?", (entity_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {"entity_id": entity_id, "outgoing_count": 0, "incoming_count": 0, "avg_strength": 0.0}

    def get_registry_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM entity_links")
            total = cursor.fetchone()["count"]
            cursor.execute("""
                SELECT link_type, COUNT(*) as count, AVG(strength) as avg_strength
                FROM entity_links GROUP BY link_type
            """)
            by_type = {row["link_type"]: {"count": row["count"], "avg_strength": row["avg_strength"]} for row in cursor.fetchall()}
            cursor.execute("""
                SELECT COUNT(DISTINCT entity_id) as count FROM (
                    SELECT source_id as entity_id FROM entity_links
                    UNION SELECT target_id as entity_id FROM entity_links
                )
            """)
            unique_entities = cursor.fetchone()["count"]
            return {
                "total_links": total,
                "unique_entities": unique_entities,
                "by_type": by_type,
                "schema_version": self.SCHEMA_VERSION,
            }

    # === Maintenance ===

    def cleanup_expired(self) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM entity_links WHERE expires_at IS NOT NULL AND expires_at < ?", (datetime.now().isoformat(),))
            deleted = cursor.rowcount
            conn.commit()
        return deleted

    def vacuum(self):
        with self._get_connection() as conn:
            conn.execute("VACUUM")

    def export(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entity_links")
            links = [EntityLink.from_row(row).to_dict() for row in cursor.fetchall()]
            return {"version": self.SCHEMA_VERSION, "exported_at": datetime.now().isoformat(), "links": links, "stats": self.get_registry_stats()}

    def import_links(self, data: Dict[str, Any], replace: bool = False) -> int:
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
                    cursor.execute("""
                        INSERT OR IGNORE INTO entity_links
                        (link_id, source_id, target_id, link_type, strength, created_at,
                         created_by, metadata, bidirectional, expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        link.link_id, link.source_id, link.target_id, link.link_type.value,
                        link.strength, link.created_at.isoformat(), link.created_by,
                        json.dumps(link.metadata), 1 if link.bidirectional else 0,
                        link.expires_at.isoformat() if link.expires_at else None,
                    ))
                    if cursor.rowcount > 0:
                        imported += 1
                except Exception:
                    continue
            conn.commit()
        return imported

    def get_link_history(self, link_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM link_history WHERE link_id = ? ORDER BY changed_at DESC", (link_id,))
            return [dict(row) for row in cursor.fetchall()]


# Global registry instance
_global_registry: Optional[LinkRegistry] = None


def get_link_registry() -> LinkRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = LinkRegistry()
    return _global_registry


def set_link_registry(registry: LinkRegistry):
    global _global_registry
    _global_registry = registry
