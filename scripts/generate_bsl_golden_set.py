#!/usr/bin/env python3
"""Generate a synthetic golden set for Phase 4 BSL retrieval benchmark.

Roadmap 260518 §6.4 (a) — selected option: Chroma generative-benchmarking
pattern, adapted to project's existing LLM rotation (claude-cli-haiku).
Created 2026-05-20.

Inputs:
  - --collection (default bsl_code_v4_late) — baseline Qdrant collection to sample from
  - --count (default 50) — number of synthetic queries to generate
  - --output (default data/bsl_golden_set.json)

What it does:
  1. Scroll N random chunks from the collection (filter by symbol_type to
     focus on functions/procedures — more answerable queries than misc).
  2. For each chunk, ask an LLM to produce a natural-language question
     about WHAT the symbol does. The chunk itself becomes the expected
     answer (module_path:line_start).
  3. Tag each item with a `slice` based on parent module file size:
       <50 KB  → small
       <300 KB → medium
       >=300 KB → god_object
  4. Write `data/bsl_golden_set.json`.

The LLM (claude-cli-haiku via llm-rotation) is called CPU-side, no GPU
contention with a running reindex.

Caveat — synthetic queries are SYNTHETIC. Human-review of the produced
JSON is recommended before drawing strong conclusions. The `id` field
should be stable across regenerations as long as scrolled points stay
the same (Qdrant scroll is deterministic-ish per offset).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def _slice_for_size(size_bytes: int) -> str:
    if size_bytes < 50_000:
        return "small"
    if size_bytes < 300_000:
        return "medium"
    return "god_object"


def _build_prompt(payload: dict[str, Any]) -> str:
    """Build LLM prompt asking for a natural-language BSL question."""
    name = payload.get("name", "?")
    symbol_type = payload.get("symbol_type", "?")
    module_name = payload.get("module_name", "?")
    content = (payload.get("content") or "")[:1500]
    return f"""Сгенерируй ОДИН вопрос на русском языке, который BSL-разработчик
мог бы задать о следующем символе. Вопрос должен быть конкретным и таким,
чтобы ИМЕННО ЭТОТ символ был лучшим ответом из всей кодовой базы.

Тип символа: {symbol_type}
Имя: {name}
Модуль: {module_name}

Код:
```bsl
{content}
```

Требования к вопросу:
1. Естественная разговорная формулировка (как разработчик в Slack)
2. НЕ упоминай точное имя символа дословно — иначе тест тривиален
3. Опиши ЦЕЛЬ/функциональность, а не реализацию
4. Длина 5-15 слов
5. Без кавычек, без вступления — только сам вопрос

Ответь ТОЛЬКО самим вопросом, одной строкой."""


def _call_llm(prompt: str) -> str | None:
    """Call project's LLMRotationService — uses configured fallback providers.

    Direct Anthropic API access via ANTHROPIC_API_KEY may be invalid in
    this venv (workspace-scoped keys, dev-mode auth). LLMRotationService
    abstracts over Zhipu/Gemini/OpenRouter/Mistral/Ollama with health
    tracking — robust for bulk batch generation.
    """
    # Lazy import to avoid forcing the heavy llm_rotation dependency at
    # module-load time (e.g. if someone imports this script for testing).
    try:
        import asyncio

        from src.shared.llm_rotation import get_service

        async def _ainvoke() -> str | None:
            service = get_service()
            result = await service.complete(prompt=prompt, max_tokens=200)
            return (result.get("text") or "").strip() or None

        # Each call gets its own event loop — simpler than threading
        # asyncio.run() through a sync caller. ~5s/call dominates anyway.
        return asyncio.run(_ainvoke())
    except Exception as e:
        print(f"  [WARN] LLM call failed: {type(e).__name__}: {e}", flush=True)
        return None


def _file_size_safe(path: str) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Generate synthetic BSL golden set")
    ap.add_argument("--collection", default="bsl_code_v4_late")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--output", type=Path, default=PROJECT_ROOT / "data" / "bsl_golden_set.json")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--qdrant-host", default="localhost")
    ap.add_argument("--qdrant-port", type=int, default=6333)
    args = ap.parse_args()

    random.seed(args.seed)

    from qdrant_client import QdrantClient

    qdrant = QdrantClient(host=args.qdrant_host, port=args.qdrant_port, timeout=60)

    # Scroll many points then sub-sample to get variety across modules.
    # 10x oversample to avoid clustering on a single big module that
    # naturally dominates the head of the scroll.
    oversample_target = max(args.count * 10, 500)
    print(f"Scrolling up to {oversample_target} points from {args.collection}...")
    candidates: list[dict[str, Any]] = []
    offset = None
    while len(candidates) < oversample_target:
        pts, offset = qdrant.scroll(
            collection_name=args.collection,
            limit=256,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        for p in pts:
            payload = p.payload or {}
            if payload.get("symbol_type") not in ("Function", "Procedure"):
                continue
            if not payload.get("name") or not payload.get("module_path"):
                continue
            if not payload.get("content"):
                continue
            candidates.append(payload)
        if offset is None:
            break
    print(f"  Got {len(candidates)} candidate symbols")

    if len(candidates) < args.count:
        print(f"  [WARN] only {len(candidates)} candidates available, requested {args.count}")
        args.count = len(candidates)

    sampled = random.sample(candidates, args.count)
    print(
        f"Generating {len(sampled)} synthetic queries via LLM "
        f"(this is sequential, ~5s per query)..."
    )

    golden: list[dict[str, Any]] = []
    failures = 0
    for idx, payload in enumerate(sampled, 1):
        prompt = _build_prompt(payload)
        t_call = time.perf_counter()
        question = _call_llm(prompt)
        elapsed = time.perf_counter() - t_call
        if not question:
            failures += 1
            print(f"  [{idx}/{len(sampled)}] FAIL ({elapsed:.1f}s) — skipped")
            continue
        size = _file_size_safe(payload["module_path"])
        slc = _slice_for_size(size)
        item = {
            "id": f"SYNTH-{idx:03d}",
            "query": question,
            "expected": [
                {
                    "module_path": payload["module_path"],
                    "line_start": int(payload.get("line_start") or 0),
                    "line_end": int(payload.get("line_end") or 0),
                }
            ],
            "slice": slc,
            "_meta": {
                "name": payload.get("name"),
                "symbol_type": payload.get("symbol_type"),
                "module_size_bytes": size,
            },
        }
        golden.append(item)
        if idx % 5 == 0 or idx == len(sampled):
            print(f"  [{idx}/{len(sampled)}] OK — slice={slc} ({elapsed:.1f}s)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as fh:
        json.dump(golden, fh, ensure_ascii=False, indent=2)
    print(f"\nWrote {len(golden)} items to {args.output} (failures: {failures})")

    # Slice distribution
    by_slice: dict[str, int] = {}
    for item in golden:
        by_slice[item["slice"]] = by_slice.get(item["slice"], 0) + 1
    print(f"Distribution: {by_slice}")
    return 0 if golden else 1


if __name__ == "__main__":
    sys.exit(main())
