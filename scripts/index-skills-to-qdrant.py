#!/usr/bin/env python3
"""Batch index SKILL.md files into Qdrant skill_library collection."""

import glob
import json
import os
import re
import sys
import uuid
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLLAMA_URL = "http://localhost:11434/api/embeddings"
QDRANT_COLLECTION = "skill_library"
VECTOR_SIZE = 768


def parse_frontmatter(content: str) -> dict:
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    meta = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")

    body_start = match.end()
    body = content[body_start:].strip()
    meta["content_preview"] = body[:2000]

    description = meta.get("description", "")
    triggers = ""
    for marker in ["Триггеры:", "Triggers:", "Триггеры: '", "triggers:"]:
        if marker.lower() in description.lower():
            idx = description.lower().index(marker.lower())
            triggers = description[idx + len(marker) :].strip()
            break
    meta["triggers"] = triggers

    return meta


def embed_text(text: str) -> list[float] | None:
    if not text.strip():
        return None
    payload = json.dumps({"model": "nomic-embed-text", "prompt": text[:8000]}).encode()
    req = Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
            return data.get("embedding")
    except (URLError, OSError) as e:
        print(f"  Embedding error: {e}", file=sys.stderr)
        return None


def ensure_collection(client: QdrantClient) -> None:
    collections = [c.name for c in client.get_collections().collections]
    if QDRANT_COLLECTION not in collections:
        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"Created collection '{QDRANT_COLLECTION}'")
    else:
        print(f"Collection '{QDRANT_COLLECTION}' already exists")


def main():
    pattern = os.path.join(PROJECT_ROOT, ".claude", "skills", "*", "SKILL.md")
    skill_files = sorted(glob.glob(pattern))

    if not skill_files:
        print("No SKILL.md files found.")
        sys.exit(0)

    print(f"Found {len(skill_files)} skill files.")

    client = QdrantClient(host="localhost", port=6333)
    ensure_collection(client)

    indexed = 0
    total = len(skill_files)

    for i, filepath in enumerate(skill_files, 1):
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        meta = parse_frontmatter(content)
        name = meta.get("name", os.path.basename(os.path.dirname(filepath)))
        description = meta.get("description", "")
        triggers = meta.get("triggers", "")
        content_preview = meta.get("content_preview", "")

        embed_input = f"{description}\n{triggers}".strip()
        if not embed_input:
            embed_input = content_preview[:1000]

        vector = embed_text(embed_input)
        if vector is None:
            print(f"  Skipped {name} (embedding failed)")
            continue

        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, name))
        rel_path = os.path.relpath(filepath, PROJECT_ROOT)

        point = PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "skill_name": name,
                "file_path": rel_path,
                "description": description,
                "triggers": triggers,
                "content_preview": content_preview[:500],
                "indexed_at": datetime.now(UTC).isoformat(),
            },
        )

        client.upsert(collection_name=QDRANT_COLLECTION, points=[point])
        indexed += 1
        print(f"Indexed {name} ({i}/{total})")

    print(f"\nDone: {indexed}/{total} skills indexed to {QDRANT_COLLECTION}")


if __name__ == "__main__":
    main()
