#!/usr/bin/env python3
"""Infrastructure for embedding and searching experience records in Qdrant."""

import argparse
import json
import sys
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

OLLAMA_URL = "http://localhost:11434/api/embeddings"
QDRANT_URL = "http://localhost:6333"
COLLECTION = "experience_bank"
VECTOR_SIZE = 768


def embed_text(text: str) -> list[float] | None:
    """Embed via Ollama nomic-embed-text. Return 768d vector or None."""
    if not text or not text.strip():
        return None
    try:
        payload = json.dumps({"model": "nomic-embed-text", "prompt": text[:8000]}).encode()
        req = Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            embedding = data.get("embedding")
            if embedding and len(embedding) == VECTOR_SIZE:
                return embedding
            print(
                f"Warning: Unexpected embedding size: {len(embedding) if embedding else 0}",
                file=sys.stderr,
            )
            return None
    except (URLError, OSError) as e:
        print(f"Warning: Embedding failed: {e}", file=sys.stderr)
        return None


def ensure_collection() -> QdrantClient:
    """Create collection if not exists, return client."""
    client = QdrantClient(url=QDRANT_URL)
    try:
        collections = [c.name for c in client.get_collections().collections]
        if COLLECTION not in collections:
            client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            print(f"Created collection '{COLLECTION}'")
        else:
            print(f"Collection '{COLLECTION}' already exists")
    except Exception as e:
        print(f"Warning: Collection check/creation failed: {e}", file=sys.stderr)
    return client


def index_experience(record: dict, client=None) -> str | None:
    """Index single experience record into Qdrant.

    ID = uuid5 from experience_id. Vector = embed(insight.reason + trigger.context_pattern).
    Returns point_id or None.
    """
    try:
        experience_id = record.get("experience_id")
        if not experience_id:
            print("Warning: Record missing 'experience_id', skipping", file=sys.stderr)
            return None

        insight = record.get("insight", {})
        trigger = record.get("trigger", {})

        insight_reason = insight.get("reason", "") if isinstance(insight, dict) else str(insight)
        context_pattern = (
            trigger.get("context_pattern", "") if isinstance(trigger, dict) else str(trigger)
        )

        embed_input = f"{insight_reason} {context_pattern}".strip()
        if not embed_input:
            print(f"Warning: Empty embed input for '{experience_id}', skipping", file=sys.stderr)
            return None

        vector = embed_text(embed_input)
        if vector is None:
            return None

        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, str(experience_id)))

        if client is None:
            client = ensure_collection()

        point = PointStruct(id=point_id, vector=vector, payload=record)
        client.upsert(collection_name=COLLECTION, points=[point])
        return point_id

    except Exception as e:
        exp_id = record.get("experience_id", "unknown")
        print(f"Warning: Failed to index '{exp_id}': {e}", file=sys.stderr)
        return None


def search_experiences(query: str, limit: int = 5) -> list[dict]:
    """Semantic search in experience_bank. Returns [{experience_id, score, insight, trigger}]."""
    try:
        vector = embed_text(query)
        if vector is None:
            return []

        client = QdrantClient(url=QDRANT_URL)
        response = client.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=limit,
            with_payload=True,
        )

        output = []
        for point in response.points:
            payload = point.payload or {}
            output.append(
                {
                    "experience_id": payload.get("experience_id"),
                    "score": point.score,
                    "insight": payload.get("insight"),
                    "trigger": payload.get("trigger"),
                }
            )
        return output

    except Exception as e:
        print(f"Warning: Search failed: {e}", file=sys.stderr)
        return []


def index_all_experiences(jsonl_path: str) -> dict:
    """Batch index from JSONL file. Returns {indexed, failed, total}."""
    path = Path(jsonl_path)
    if not path.exists():
        print(f"Warning: File not found: {jsonl_path}", file=sys.stderr)
        return {"indexed": 0, "failed": 0, "total": 0}

    client = ensure_collection()
    indexed = 0
    failed = 0
    total = 0

    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON on line {line_num}: {e}", file=sys.stderr)
                failed += 1
                total += 1
                continue

            total += 1
            result = index_experience(record, client=client)
            if result is not None:
                indexed += 1
            else:
                failed += 1

    return {"indexed": indexed, "failed": failed, "total": total}


def main():
    """CLI: python experience-embedder.py [--index PATH | --search QUERY | --ensure]"""
    parser = argparse.ArgumentParser(description="Embed and search experience records in Qdrant")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--index", metavar="PATH", help="Batch index from JSONL file")
    group.add_argument("--search", metavar="QUERY", help="Semantic search in experience bank")
    group.add_argument("--ensure", action="store_true", help="Ensure collection exists")

    args = parser.parse_args()

    if args.ensure:
        ensure_collection()
    elif args.index:
        results = index_all_experiences(args.index)
        print(
            f"Indexing complete: {results['indexed']}/{results['total']} indexed, {results['failed']} failed"
        )
    elif args.search:
        results = search_experiences(args.search)
        if not results:
            print("No results found.")
        else:
            for i, result in enumerate(results, 1):
                print(f"\n--- Result {i} (score: {result['score']:.4f}) ---")
                print(f"  experience_id: {result['experience_id']}")
                print(
                    f"  insight: {json.dumps(result['insight'], ensure_ascii=False, indent=2) if result['insight'] else 'N/A'}"
                )


if __name__ == "__main__":
    main()
