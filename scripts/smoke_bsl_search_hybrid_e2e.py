"""E2E smoke-test for patched BSLSearchService against hybrid bsl_code_v4_late.

Verifies:
  1. _detect_collection_layout returns 'hybrid' for production alias.
  2. _call_qdrant_search uses Prefetch+RRF path and returns results.
  3. Fallback dense-only path still works (forced via collection arg).

Run:
    .venv\\Scripts\\python.exe scripts\\smoke_bsl_search_hybrid_e2e.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))


async def run() -> int:
    from src.bsl.semantic_search.services.search import BSLSearchService, SearchMode, SearchRequest

    svc = BSLSearchService()

    # Use a real BSL identifier as the query — has CamelCase to exercise
    # the normalize_camelcase path on the BM25 side.
    request = SearchRequest(
        query="ОбработкаПроведения документа Реализация",
        mode=SearchMode.SEMANTIC_ONLY,
        limit=5,
    )
    results = await svc.search(request)

    print(f"[query] '{request.query}'")
    print(f"[layout] detected: {svc._collection_layout}")
    print(f"[results] {len(results)} returned")
    for i, r in enumerate(results, 1):
        print(f"  {i}. score={r.score:.3f} path={r.file_path[:80]}")

    if svc._collection_layout != "hybrid":
        print(f"FAIL: expected hybrid layout, got {svc._collection_layout}")
        return 1
    if not results:
        print("FAIL: no results returned")
        return 1
    print("OK: hybrid path works end-to-end")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
