"""Phase 8.12.3 - Smoke: collection sizes + bsl_code_v4 search via TEI HTTP."""

import json
import os
import sys
import time

import httpx
from qdrant_client import QdrantClient

LOG_DIR = os.path.dirname(os.path.abspath(__file__))
QUERIES_PATH = os.path.join(LOG_DIR, "8.12.3_queries.json")
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080")
QWEN3_QUERY_INSTR = (
    "Instruct: Given a web search query, retrieve relevant passages "
    "that answer the query\nQuery: "
)


def embed_via_tei(text: str) -> list:
    """Match Qwen3TEIEmbedder query path: prepend retrieval-instruction."""
    payload = {"inputs": [QWEN3_QUERY_INSTR + text]}
    r = httpx.post(f"{TEI_URL}/embed", json=payload, timeout=60.0)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, list) and data and isinstance(data[0], list):
        return data[0]
    if isinstance(data, dict) and "data" in data:
        return data["data"][0]["embedding"]
    raise RuntimeError(f"Unexpected TEI response shape: {type(data).__name__}")


client = QdrantClient(host="localhost", port=6333, timeout=30)
print("Collection points_count:")
for c in sorted(client.get_collections().collections, key=lambda x: x.name):
    info = client.get_collection(collection_name=c.name)
    print("  %-32s %8d" % (c.name, info.points_count))

with open(QUERIES_PATH, "r", encoding="utf-8") as f:
    queries = json.load(f)

print("\nQuerying TEI %s ..." % TEI_URL)
for q in queries:
    t0 = time.time()
    qv = embed_via_tei(q)
    embed_ms = (time.time() - t0) * 1000
    res = client.query_points(collection_name="bsl_code_v4", query=qv, limit=3, with_payload=True).points
    print("\nQuery: %r  (embed=%.1fms)" % (q, embed_ms))
    for r in res:
        name = r.payload.get("name", "?")
        mod = r.payload.get("module_name", "?")
        print("  score=%.4f  name=%s  module=%s" % (r.score, name, mod))

print("\nSmoke OK.")
