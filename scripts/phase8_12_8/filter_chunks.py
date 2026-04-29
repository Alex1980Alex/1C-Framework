"""Phase 8.12.8 Step 1: filter chunks via LLM-judge."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402,F401

JUDGE_CRITERION = (
    "Содержит осмысленную BSL-логику 1С: не пустой `КонецПроцедуры`, "
    "не тривиальный getter/setter, не synthetic module_summary."
)
JUDGE_PROMPT = """Evaluate the document against the criterion: {criterion}
Document:
{content}

Output exactly "yes" or "no" — no other text.
"""

import argparse
import json
import time
from typing import Any, Generator

from qdrant_client import QdrantClient


def call_z_ai(prompt: str) -> str:
    from scripts.phase8_12_8._llm import llm_complete
    return llm_complete(prompt, max_tokens=8, temperature=0.0)


def scroll_chunks(client: QdrantClient, collection: str, batch: int = 256) -> Generator[Any, None, None]:
    offset = None
    while True:
        records, next_offset = client.scroll(
            collection_name=collection, limit=batch, offset=offset,
            with_payload=True, with_vectors=False,
        )
        if not records:
            break
        for rec in records:
            yield rec
        offset = next_offset
        if offset is None:
            break


def judge_chunk(content: str, llm_call) -> tuple[bool, str]:
    truncated = content[:4000]
    prompt = JUDGE_PROMPT.format(criterion=JUDGE_CRITERION, content=truncated)
    raw = llm_call(prompt)
    return raw.strip().lower() == "yes", raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--output", type=Path, default=config.CHUNKS_FILTERED)
    args = parser.parse_args()

    client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT, timeout=30)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    kept_count = dropped_count = total = 0
    start = time.time()

    with open(args.output, "w", encoding="utf-8") as f:
        for chunk in scroll_chunks(client, config.COLL_QWEN3):
            if args.limit is not None and total >= args.limit:
                break
            content: str = (chunk.payload or {}).get("content", "")
            if args.skip_llm:
                stripped = content.strip()
                if len(content) < 100:
                    kept, reason = False, "heuristic: too short"
                elif stripped in ("КонецПроцедуры", "КонецФункции"):
                    kept, reason = False, "heuristic: trivial block"
                else:
                    kept, reason = True, "heuristic: passed"
            else:
                kept, reason = judge_chunk(content, call_z_ai)
            f.write(json.dumps({
                "id": str(chunk.id), "content": content,
                "payload": chunk.payload, "kept": kept, "reason": reason,
            }, ensure_ascii=False) + "\n")
            total += 1
            kept_count += int(kept)
            dropped_count += int(not kept)
            if total % 100 == 0:
                print(f"[{total}] kept={kept_count} dropped={dropped_count} {time.time()-start:.1f}s")

    ratio = kept_count / total if total else 0.0
    print(f"Done: total={total} kept={kept_count} dropped={dropped_count} ratio={ratio:.4f} ({time.time()-start:.1f}s)")


if __name__ == "__main__":
    main()
