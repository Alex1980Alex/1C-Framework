#!/usr/bin/env python3
"""
Auto-reindex 1C:Enterprise configuration metadata into Qdrant — Phase 9

Pipeline:
1. Export metadata via 1c-mcp-crud HTTP API (get_metadata)
2. Parse metadata tree into flat MetadataRecord records
3. Incremental update with SHA-256 hash comparison
4. Qdrant upsert with embeddings (nomic-embed-text via Ollama)

Usage:
    python reindex_metadata.py              # incremental
    python reindex_metadata.py --full       # full reindex
    python reindex_metadata.py --dry-run    # show what would change
"""

import argparse
import hashlib
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, PointStruct, VectorParams

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class MetadataRecord:
    """Flat metadata record for Qdrant embedding."""

    full_path: str
    object_type: str
    object_name: str
    synonym: str
    attributes: list[str] = field(default_factory=list)
    table_parts: list[str] = field(default_factory=list)
    description: str = ""
    content_hash: str = ""

    def generate_description(self) -> str:
        parts = [f"{self.object_type}: {self.synonym or self.object_name}"]
        if self.attributes:
            parts.append(f"Реквизиты: {', '.join(self.attributes[:8])}")
            if len(self.attributes) > 8:
                parts.append(f"...и ещё {len(self.attributes) - 8}")
        if self.table_parts:
            parts.append(f"Табличные части: {', '.join(self.table_parts)}")
        return ". ".join(parts)

    def compute_hash(self) -> str:
        serialized = json.dumps(
            {
                "full_path": self.full_path,
                "object_type": self.object_type,
                "object_name": self.object_name,
                "synonym": self.synonym,
                "attributes": sorted(self.attributes),
                "table_parts": sorted(self.table_parts),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class MetadataIndexer:
    """Pipeline for metadata export -> parse -> embed -> upsert."""

    def __init__(
        self,
        mcp_url: str = "http://localhost:6003/mcp",
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        ollama_url: str = "http://localhost:11434",
        cache_dir: str = "cache",
    ):
        self.mcp_url = mcp_url
        self.qdrant = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.ollama_url = ollama_url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.hashes_file = self.cache_dir / "metadata_hashes.json"
        self.collection = "metadata_1c"
        self.dim = 768
        self.model = "nomic-embed-text"

    # --- Export ---

    def export_metadata(self, path: str = "/") -> dict:
        logger.info("Exporting metadata from %s via %s", path, self.mcp_url)
        try:
            resp = requests.post(
                self.mcp_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "id": 1,
                    "params": {"name": "get_metadata", "arguments": {"path": path}},
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                logger.error("MCP error: %s", data["error"])
                return {}
            return data.get("result", {})
        except requests.RequestException as e:
            logger.error("Export failed: %s", e)
            return {}

    # --- Parse ---

    def parse_tree(self, metadata: dict, parent: str = "") -> list[MetadataRecord]:
        records = []
        if not isinstance(metadata, dict):
            return records
        for name, obj in metadata.items():
            if not isinstance(obj, dict):
                continue
            full_path = f"{parent}.{name}" if parent else name
            rec = MetadataRecord(
                full_path=full_path,
                object_type=obj.get("type", parent.split(".")[0] if parent else ""),
                object_name=name,
                synonym=obj.get("synonym", name),
                attributes=obj.get("attributes", []),
                table_parts=obj.get("table_parts", []),
            )
            rec.description = rec.generate_description()
            rec.content_hash = rec.compute_hash()
            records.append(rec)
            if "children" in obj and isinstance(obj["children"], dict):
                records.extend(self.parse_tree(obj["children"], full_path))
        return records

    # --- Hashes ---

    def load_hashes(self) -> dict[str, str]:
        if self.hashes_file.exists():
            try:
                return json.loads(self.hashes_file.read_text("utf-8"))
            except Exception:
                return {}
        return {}

    def save_hashes(self, hashes: dict[str, str]) -> None:
        self.hashes_file.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), "utf-8")

    # --- Embedding ---

    def embed(self, text: str) -> list[float]:
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/embed",
                json={"model": self.model, "input": text},
                timeout=30,
            )
            resp.raise_for_status()
            vecs = resp.json().get("embeddings", [[]])
            return vecs[0] if vecs and len(vecs[0]) == self.dim else [0.0] * self.dim
        except Exception as e:
            logger.warning("Embedding failed: %s", e)
            return [0.0] * self.dim

    # --- Qdrant ---

    def ensure_collection(self) -> None:
        try:
            self.qdrant.get_collection(self.collection)
        except Exception:
            self.qdrant.create_collection(
                self.collection,
                vectors_config=VectorParams(size=self.dim, distance=Distance.COSINE),
            )
            logger.info("Created collection %s", self.collection)

    def upsert(self, records: list[MetadataRecord], dry_run: bool = False) -> tuple[int, int, int]:
        self.ensure_collection()
        prev = self.load_hashes()
        curr: dict[str, str] = {}
        inserted, updated = 0, 0

        for i, rec in enumerate(records):
            curr[rec.full_path] = rec.content_hash
            if rec.full_path in prev and prev[rec.full_path] == rec.content_hash:
                continue
            action = "UPDATE" if rec.full_path in prev else "INSERT"
            if dry_run:
                logger.info("[DRY-RUN] %s %s", action, rec.full_path)
                continue

            logger.info("[%d/%d] %s %s", i + 1, len(records), action, rec.full_path)
            vec = self.embed(rec.description)
            self.qdrant.upsert(
                self.collection,
                [
                    PointStruct(
                        id=hash(rec.full_path) & 0x7FFFFFFF,
                        vector=vec,
                        payload=asdict(rec),
                    )
                ],
            )
            if action == "UPDATE":
                updated += 1
            else:
                inserted += 1

        deleted = 0
        if not dry_run:
            for fp in prev:
                if fp not in curr:
                    try:
                        self.qdrant.delete(self.collection, points_selector=[hash(fp) & 0x7FFFFFFF])
                        deleted += 1
                        logger.info("DELETED %s", fp)
                    except Exception as e:
                        logger.warning("Delete failed for %s: %s", fp, e)
            self.save_hashes(curr)

        return inserted, updated, deleted

    # --- MD/CSV Export ---

    def export_md(self, records: list[MetadataRecord], output_dir: Path) -> None:
        """Export metadata records to Markdown files grouped by object_type."""
        output_dir.mkdir(parents=True, exist_ok=True)
        by_type: dict[str, list[MetadataRecord]] = {}
        for rec in records:
            by_type.setdefault(rec.object_type or "Other", []).append(rec)

        for obj_type, recs in sorted(by_type.items()):
            md_path = output_dir / f"{obj_type}.md"
            lines = [f"# {obj_type} ({len(recs)})\n"]
            for rec in sorted(recs, key=lambda r: r.object_name):
                lines.append(f"\n## {rec.synonym or rec.object_name}")
                lines.append(f"\n**Путь:** `{rec.full_path}`\n")
                if rec.attributes:
                    lines.append(f"**Реквизиты:** {', '.join(rec.attributes[:15])}")
                    if len(rec.attributes) > 15:
                        lines.append(f" ...и ещё {len(rec.attributes) - 15}")
                    lines.append("")
                if rec.table_parts:
                    lines.append(f"**Табличные части:** {', '.join(rec.table_parts)}\n")
            md_path.write_text("\n".join(lines), "utf-8")
            logger.info("Exported %s: %d objects -> %s", obj_type, len(recs), md_path)

    def export_csv(self, records: list[MetadataRecord], output_path: Path) -> None:
        """Export metadata records to CSV."""
        import csv

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(
                ["full_path", "object_type", "object_name", "synonym", "attributes", "table_parts"]
            )
            for rec in sorted(records, key=lambda r: r.full_path):
                w.writerow(
                    [
                        rec.full_path,
                        rec.object_type,
                        rec.object_name,
                        rec.synonym,
                        ";".join(rec.attributes),
                        ";".join(rec.table_parts),
                    ]
                )
        logger.info("Exported CSV: %d records -> %s", len(records), output_path)

    # --- Run ---

    def run(self, full: bool = False, dry_run: bool = False, fmt: str = "qdrant") -> None:
        if full:
            self.hashes_file.unlink(missing_ok=True)

        metadata = self.export_metadata("/")
        if not metadata:
            logger.error("No metadata exported — check MCP toolkit connection")
            return

        records = self.parse_tree(metadata)
        logger.info("Parsed %d metadata records", len(records))

        if fmt == "md":
            self.export_md(records, self.cache_dir / "metadata-md")
            return
        elif fmt == "csv":
            self.export_csv(records, self.cache_dir / "metadata.csv")
            return

        ins, upd, dlt = self.upsert(records, dry_run)
        logger.info(
            "Done: %d inserted, %d updated, %d deleted%s",
            ins,
            upd,
            dlt,
            " [DRY-RUN]" if dry_run else "",
        )


def main():
    p = argparse.ArgumentParser(description="Reindex 1C metadata to Qdrant")
    p.add_argument("--full", action="store_true", help="Full reindex (clear hash cache)")
    p.add_argument("--dry-run", action="store_true", help="Preview changes only")
    p.add_argument(
        "--format", choices=["qdrant", "md", "csv"], default="qdrant", help="Output format"
    )
    p.add_argument("--mcp-url", default="http://localhost:6003/mcp")
    p.add_argument("--qdrant-host", default="localhost")
    p.add_argument("--qdrant-port", type=int, default=6333)
    p.add_argument("--ollama-url", default="http://localhost:11434")
    p.add_argument("--cache-dir", default="cache")
    args = p.parse_args()

    indexer = MetadataIndexer(
        mcp_url=args.mcp_url,
        qdrant_host=args.qdrant_host,
        qdrant_port=args.qdrant_port,
        ollama_url=args.ollama_url,
        cache_dir=args.cache_dir,
    )

    try:
        indexer.run(full=args.full, dry_run=args.dry_run, fmt=args.format)
    except Exception as e:
        logger.error("Reindex failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
