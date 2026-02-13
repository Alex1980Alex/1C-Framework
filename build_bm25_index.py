"""Build BM25 FTS5 index from Qdrant vector store.

Reads all chunks from Qdrant (with content + metadata) and inserts
into the SQLite FTS5 BM25 index with pymorphy3 lemmatization.
Phase 27: Multi-column FTS5 (title + body) with 10x title boost.

Usage:
    python build_bm25_index.py          # full rebuild
    python build_bm25_index.py --clear  # clear + rebuild
"""

import sys
import io
import asyncio
import re
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.pdf_framework.config import get_settings
from src.pdf_framework.search.bm25_store import BM25Store
from src.pdf_framework.vector_store import get_vector_store


# Pattern to detect numbered section headings in bold: **4.7.4. Title**
_HEADING_BOLD_RE = re.compile(
    r"\*\*(\d+(?:\.\d+)+\.?)\s*\.?\s*([^*]+?)\*\*"
)

# Pattern to detect Docling markdown headings: ## 5 . 5 . 12 . 2 . Title
_HEADING_MD_RE = re.compile(
    r"^#{1,6}\s+((?:\d+\s*\.\s*)+\d*\.?\s*)(.+)$", re.MULTILINE
)


def _normalize_number(num_str: str) -> str:
    """Normalize a number string: '5 . 5 . 12 . 2 .' → '5.5.12.2'."""
    return re.sub(r"\s*\.\s*", ".", num_str).strip().rstrip(".")


def propagate_section_headers(chunks: list[dict]) -> int:
    """Infer parent section headers from chunk content and propagate to neighbors.

    Supports both formats:
    - Bold: **4.7.4. Title**
    - Markdown: ## 5 . 5 . 12 . 2 . Title (Docling format with spaces)

    Returns number of chunks that received a propagated header.
    """
    from collections import defaultdict
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        by_doc[c["document_id"]].append(c)

    propagated = 0
    for doc_id, doc_chunks in by_doc.items():
        doc_chunks.sort(key=lambda c: c.get("chunk_index", 0))

        current_headings: dict[int, str] = {}

        for c in doc_chunks:
            if c.get("section"):
                continue

            # Scan for both bold and markdown heading patterns
            found_headings = []

            # Bold format: **4.7.4. Title**
            for match in _HEADING_BOLD_RE.finditer(c["content"]):
                num_part = match.group(1).rstrip(".")
                title = match.group(2).strip()
                level = num_part.count(".") + 1
                heading = f"{num_part}. {title}"
                found_headings.append((match.start(), level, heading))

            # Markdown format: ## 5 . 5 . 12 . 2 . Title
            for match in _HEADING_MD_RE.finditer(c["content"]):
                raw_num = match.group(1)
                title = match.group(2).strip()
                # Skip figures
                if title.lower().startswith("рис."):
                    continue
                num_part = _normalize_number(raw_num)
                if not num_part or not num_part[0].isdigit():
                    continue
                level = num_part.count(".") + 1
                heading = f"{num_part}. {title}"
                found_headings.append((match.start(), level, heading))

            # Sort by position and apply
            found_headings.sort(key=lambda x: x[0])
            for _, level, heading in found_headings:
                current_headings[level] = heading
                for deeper in list(current_headings):
                    if deeper > level:
                        del current_headings[deeper]

            if current_headings and not c.get("section"):
                sorted_levels = sorted(current_headings.keys())
                # Use deepest heading as section title
                c["section"] = current_headings[sorted_levels[-1]]
                propagated += 1

    return propagated


async def read_qdrant_chunks() -> list[dict]:
    """Read all chunks from Qdrant vector store."""
    settings = get_settings()
    store = get_vector_store(settings.vector_store)
    await store.initialize()

    total = await store.count()
    print(f"Qdrant collection: {total} points")

    if total == 0:
        return []

    # Scroll all chunks
    all_chunks = await store.scroll(limit=total + 100)
    print(f"Scrolled {len(all_chunks)} chunks from Qdrant")

    chunks = []
    for chunk in all_chunks:
        if not chunk.content or not chunk.content.strip():
            continue

        # Phase 29: Prefer breadcrumb (full hierarchy) for BM25 title column
        section = (
            chunk.metadata.get("breadcrumb", "")
            or chunk.section
            or chunk.metadata.get("section_title", "")
            or ""
        )
        if section == "None":
            section = ""

        chunks.append({
            "id": chunk.id,
            "content": chunk.content,
            "document_id": chunk.document_id,
            "source": chunk.metadata.get("source", ""),
            "section": section,
            "chunk_index": chunk.chunk_index or 0,
        })

    return chunks


async def main():
    clear_flag = "--clear" in sys.argv

    settings = get_settings()

    # Initialize BM25 store
    bm25 = BM25Store(db_path=settings.search.bm25_db_path)
    await bm25.initialize()

    existing = await bm25.count()
    print(f"BM25 index: {existing} chunks already indexed\n")

    if existing > 0 or clear_flag:
        print("Clearing existing BM25 index...")
        await bm25.clear()

    print("=== Reading from Qdrant ===")

    # Read chunks from Qdrant
    t0 = time.time()
    chunks = await read_qdrant_chunks()
    print(f"\nExtracted {len(chunks)} chunks from Qdrant ({time.time() - t0:.1f}s)")

    if not chunks:
        print("No chunks found. Cannot build BM25 index.")
        return

    # Propagate section headers from headings found in chunk content
    propagated = propagate_section_headers(chunks)
    with_section = sum(1 for c in chunks if c.get("section"))
    print(f"Section headers: {with_section} chunks have sections ({propagated} propagated from content)")

    # Insert into BM25 in batches
    batch_size = 500
    indexed = 0
    t0 = time.time()

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        added = await bm25.add_chunks(
            chunk_ids=[c["id"] for c in batch],
            contents=[c["content"] for c in batch],
            document_ids=[c["document_id"] for c in batch],
            sources=[c["source"] for c in batch],
            sections=[c.get("section", "") for c in batch],
        )
        indexed += added
        elapsed = time.time() - t0
        print(f"  [{min(i + batch_size, len(chunks))}/{len(chunks)}] {indexed} indexed ({elapsed:.1f}s)", flush=True)

    elapsed = time.time() - t0
    final_count = await bm25.count()
    print(f"\nDone: {final_count} chunks in BM25 index ({elapsed:.1f}s)")
    print(f"Schema: multi-column FTS5 (title=10x, body=1x)")


if __name__ == "__main__":
    asyncio.run(main())
