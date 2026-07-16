"""
Merge Patterns — Pattern deduplication and conflict resolution for skill_learning.

Handles merging of duplicate patterns found in JSONL storage:
- Content-based deduplication (normalized text matching)
- Confidence-based conflict resolution (keep higher confidence)
- Tag merging (union of tags)
- Application count aggregation

Version: 1.0 (2026-04-04) — P1 migration
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ConflictStrategy(str):
    """Strategy for resolving merge conflicts."""

    KEEP_HIGHER_CONFIDENCE = "keep_higher_confidence"
    KEEP_NEWER = "keep_newer"
    KEEP_OLDER = "keep_older"
    MERGE_ALL = "merge_all"


@dataclass
class PatternRecord:
    """A single pattern from JSONL storage.

    Fields this schema does not declare are carried in :attr:`extra` and written back
    verbatim (roadmap 260716 P1.1). Reason: the silo is written by several producers
    whose schema is WIDER than this one — `archived`, `content_hash`,
    `evidence_sources`, `original_pattern_type`. The merge job rewrites the whole
    file, so "field this dataclass doesn't know" used to mean "field deleted from
    disk on the next cadence run": archived records came back to life (and got
    re-harvested into Qdrant), and the `content_hash` quarantine dedup went blind.
    """

    pattern_id: str
    pattern_type: str = "workflow-pattern"
    name: str = ""
    content: str = ""
    description: str = ""
    confidence: float = 0.7
    tags: list[str] = field(default_factory=list)
    application_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def normalized_content(self) -> str:
        """Lowercase, whitespace-normalized content for comparison."""
        return " ".join(self.content.lower().split())

    def to_dict(self) -> dict[str, Any]:
        # `extra` first so the declared fields always win the merge: a stale copy of a
        # known key in `extra` must never shadow the parsed (and possibly merged) value.
        return {
            **self.extra,
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "name": self.name,
            "content": self.content,
            "description": self.description,
            "confidence": self.confidence,
            "tags": self.tags,
            "application_count": self.application_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PatternRecord":
        fields = cls.__dataclass_fields__
        # "extra" itself is never consumed positionally: a literal `extra` key in the
        # silo is just another unknown field and round-trips through the bucket.
        known = {k: v for k, v in data.items() if k in fields and k != "extra"}
        unknown = {k: v for k, v in data.items() if k not in fields or k == "extra"}
        return cls(**known, extra=unknown)


@dataclass
class MergeResult:
    """Result of a pattern merge operation."""

    duplicates_found: int
    patterns_merged: int
    patterns_kept: int
    space_saved_bytes: int = 0
    merged_ids: list[str] = field(default_factory=list)
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "duplicates_found": self.duplicates_found,
            "patterns_merged": self.patterns_merged,
            "patterns_kept": self.patterns_kept,
            "space_saved_bytes": self.space_saved_bytes,
            "merged_ids": self.merged_ids,
            "details": self.details,
        }


class PatternMerger:
    """
    Merges duplicate patterns in JSONL-based skill_learning storage.

    Usage:
        merger = PatternMerger(storage_dir=Path("data/skill_learning"))
        result = await merger.merge_duplicates(strategy="keep_higher_confidence")
    """

    def __init__(
        self,
        storage_dir: Path,
        strategy: str = ConflictStrategy.KEEP_HIGHER_CONFIDENCE,
        similarity_threshold: float = 0.85,
    ):
        self.storage_dir = storage_dir
        self.patterns_file = storage_dir / "patterns.jsonl"
        self.strategy = strategy
        self.similarity_threshold = similarity_threshold

    async def merge_duplicates(
        self, strategy: str | None = None, dry_run: bool = False
    ) -> MergeResult:
        """
        Find and merge duplicate patterns.

        Args:
            strategy: Override default conflict strategy
            dry_run: If True, don't write changes — just report

        Returns:
            MergeResult with statistics
        """
        strategy = strategy or self.strategy
        patterns, unreadable = await self._load_patterns()

        if not patterns:
            return MergeResult(duplicates_found=0, patterns_merged=0, patterns_kept=len(patterns))

        # Group by normalized content
        groups: dict[str, list[PatternRecord]] = {}
        for p in patterns:
            key = p.normalized_content
            if key not in groups:
                groups[key] = []
            groups[key].append(p)

        # Also check name-based duplicates
        by_name: dict[str, list[PatternRecord]] = {}
        for p in patterns:
            name_key = p.name.lower().strip()
            if name_key:
                if name_key not in by_name:
                    by_name[name_key] = []
                by_name[name_key].append(p)

        # Merge groups
        duplicates_found = 0
        patterns_merged = 0
        merged_ids: list[str] = []
        details: list[dict[str, Any]] = []
        final_patterns: dict[str, PatternRecord] = {}

        for key, group in groups.items():
            if len(group) == 1:
                final_patterns[group[0].pattern_id] = group[0]
                continue

            duplicates_found += len(group) - 1
            winner = self._resolve_conflict(group, strategy)
            merged = self._merge_records(group, winner)

            final_patterns[merged.pattern_id] = merged
            patterns_merged += len(group) - 1
            merged_ids.extend(p.pattern_id for p in group if p.pattern_id != merged.pattern_id)

            details.append(
                {
                    "winner_id": merged.pattern_id,
                    "merged_count": len(group) - 1,
                    "merged_ids": [
                        p.pattern_id for p in group if p.pattern_id != merged.pattern_id
                    ],
                    "confidence": merged.confidence,
                }
            )

        # Write if not dry run
        if not dry_run and patterns_merged > 0:
            await self._write_patterns(list(final_patterns.values()), unreadable)

        # Estimate space saved
        original_size = sum(len(json.dumps(p.to_dict())) for p in patterns)
        merged_size = sum(len(json.dumps(p.to_dict())) for p in final_patterns.values())

        return MergeResult(
            duplicates_found=duplicates_found,
            patterns_merged=patterns_merged,
            patterns_kept=len(final_patterns),
            space_saved_bytes=max(0, original_size - merged_size),
            merged_ids=merged_ids,
            details=details,
        )

    async def find_duplicates(self) -> list[list[PatternRecord]]:
        """Find groups of duplicate patterns without merging."""
        patterns, _unreadable = await self._load_patterns()
        groups: dict[str, list[PatternRecord]] = {}
        for p in patterns:
            key = p.normalized_content
            if key not in groups:
                groups[key] = []
            groups[key].append(p)

        return [g for g in groups.values() if len(g) > 1]

    def _resolve_conflict(self, group: list[PatternRecord], strategy: str) -> PatternRecord:
        """Select the winning record from a duplicate group."""
        if strategy == ConflictStrategy.KEEP_HIGHER_CONFIDENCE:
            return max(group, key=lambda p: p.confidence)
        elif strategy == ConflictStrategy.KEEP_NEWER:
            return max(group, key=lambda p: p.updated_at or p.created_at)
        elif strategy == ConflictStrategy.KEEP_OLDER:
            return min(group, key=lambda p: p.created_at)
        else:  # MERGE_ALL — use highest confidence as base
            return max(group, key=lambda p: p.confidence)

    def _merge_records(self, group: list[PatternRecord], winner: PatternRecord) -> PatternRecord:
        """Merge metadata from all records into the winner.

        The winner's ``extra`` survives as-is — losers' unknown fields are NOT folded
        in. Folding is unsound for a bucket whose semantics this class does not know.

        ``archived`` is the one exception, because it is the field that decides whether
        the fact still exists. Making it durable (P1.1) without teaching the merge about
        it just inverts the old bug: the winner is chosen by confidence, so an archived
        record with conf 0.9 beating a live one with conf 0.4 would collapse the group
        to an ARCHIVED record and delete the live copy from the silo — after which
        `pattern_harvest` skips the fact entirely. Before P1.1 the same input
        resurrected the archived record. Both are wrong.

        The rule that is not wrong follows §22 revive-on-recurrence: a duplicate that is
        live means the fact came back, so the merged record is archived ONLY if every
        member was. Archival is a claim about the fact, not about one copy of it.
        """
        if any(not r.extra.get("archived") for r in group):
            winner.extra.pop("archived", None)
            winner.extra.pop("expired_at", None)

        merged_tags: set[str] = set(winner.tags)
        total_applications = winner.application_count
        max_version = winner.version

        for record in group:
            if record.pattern_id == winner.pattern_id:
                continue
            merged_tags.update(record.tags)
            total_applications += record.application_count
            max_version = max(max_version, record.version)

        winner.tags = sorted(merged_tags)
        winner.application_count = total_applications
        winner.version = max_version + 1
        winner.updated_at = datetime.now().isoformat()

        return winner

    # ----- IO -----

    async def _load_patterns(self) -> tuple[list[PatternRecord], list[str]]:
        """Load all patterns from the JSONL file.

        Returns ``(records, unreadable)`` where *unreadable* holds the raw text of
        every line this merger could not parse. They are handed back so
        :meth:`_write_patterns` can return them to disk untouched: this job rewrites
        the whole silo, so dropping a line at read time is not "skip", it is DELETE.
        A hand-edited or half-flushed line is a bug to look at, not data to discard.
        """
        if not self.patterns_file.exists():
            return ([], [])

        patterns: list[PatternRecord] = []
        unreadable: list[str] = []

        def _load():
            with open(self.patterns_file, encoding="utf-8") as f:
                for line in f:
                    raw = line.rstrip("\n")
                    if not raw.strip():
                        continue
                    try:
                        patterns.append(PatternRecord.from_dict(json.loads(raw)))
                    except Exception:
                        # Broad on purpose: a non-dict JSON value (`123`, `"x"`, `[]`)
                        # parses fine and then dies on .items() — an uncaught
                        # AttributeError here used to abort the whole cadence job.
                        unreadable.append(raw)

        await asyncio.to_thread(_load)
        if unreadable:
            logger.warning(
                "%d unreadable line(s) in %s — preserved verbatim, not merged",
                len(unreadable),
                self.patterns_file,
            )
        return (patterns, unreadable)

    async def _write_patterns(
        self, patterns: list[PatternRecord], unreadable: list[str] | None = None
    ) -> None:
        """Write patterns back to the JSONL file, re-appending unreadable lines."""
        unreadable = unreadable or []

        def _write():
            # Backup original
            backup = self.patterns_file.with_suffix(".jsonl.bak")
            if self.patterns_file.exists():
                import shutil

                shutil.copy2(self.patterns_file, backup)

            with open(self.patterns_file, "w", encoding="utf-8") as f:
                for p in patterns:
                    f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")
                # Verbatim, at the end: the silo is a set of records, so position
                # carries no meaning (the merge already regroups), but survival does.
                for raw in unreadable:
                    f.write(raw + "\n")

        await asyncio.to_thread(_write)
        logger.info(
            "Wrote %d patterns after merge (+%d preserved unreadable)",
            len(patterns),
            len(unreadable),
        )


__all__ = [
    "ConflictStrategy",
    "MergeResult",
    "PatternMerger",
    "PatternRecord",
]
