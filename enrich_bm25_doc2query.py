"""Enrich BM25 index with doc2query: generate synthetic queries per chunk.

Uses Claude Sonnet via Z.AI to generate 3-5 search queries per chunk.
Generated queries are stored in FTS5 title column (10x weight boost),
dramatically improving recall for user queries that don't match exact terms.

Phase 27 / P3.2: doc2query enrichment for section-aware search.

Usage:
    python enrich_bm25_doc2query.py              # enrich all chunks
    python enrich_bm25_doc2query.py --limit 10   # test on 10 chunks
    python enrich_bm25_doc2query.py --rebuild     # rebuild FTS5 after enrichment
"""

import sys
import io
import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
sys.path.insert(0, str(Path(__file__).parent))

from src.pdf_framework.config import get_settings
from src.pdf_framework.search.bm25_store import BM25Store, lemmatize_text

logger = logging.getLogger(__name__)

# Prompt for generating search queries from a chunk
_DOC2QUERY_SYSTEM = (
    "Ты генерируешь поисковые запросы на русском языке. "
    "По тексту документа создай 3-5 коротких запросов, "
    "которые пользователь мог бы ввести, чтобы найти именно этот фрагмент. "
    "Запросы должны быть разнообразными: фактические, аналитические, терминологические. "
    "Верни ТОЛЬКО JSON-массив строк, без пояснений."
)

_DOC2QUERY_USER = """Раздел: {section}

Текст фрагмента:
{content}

Сгенерируй 3-5 поисковых запросов для этого фрагмента. Формат: ["запрос1", "запрос2", ...]"""


async def generate_queries_batch(
    chunks: list[dict],
    api_key: str,
    base_url: str,
    model: str = "claude-sonnet-4-5-20250929",
    concurrency: int = 5,
) -> dict[str, list[str]]:
    """Generate doc2query for a batch of chunks using async Anthropic client.

    Returns dict of chunk_id -> list of generated queries.
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url or None)
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, list[str]] = {}

    async def process_one(chunk: dict) -> tuple[str, list[str]]:
        async with semaphore:
            cid = chunk["chunk_id"]
            content = chunk["original_content"][:1500]  # Limit to ~1500 chars
            section = chunk.get("section_title", "")

            prompt = _DOC2QUERY_USER.format(
                section=section or "(не указан)",
                content=content,
            )

            for attempt in range(2):
                try:
                    response = await client.messages.create(
                        model=model,
                        max_tokens=256,
                        temperature=0.3,
                        system=_DOC2QUERY_SYSTEM,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    text = response.content[0].text.strip()

                    # Parse JSON array
                    # Handle markdown code blocks
                    if text.startswith("```"):
                        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

                    queries = json.loads(text)
                    if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
                        return cid, queries[:5]

                    # Retry if format is wrong
                    logger.warning("[DOC2QUERY] Bad format for %s: %s", cid[:16], text[:100])
                except json.JSONDecodeError:
                    logger.warning("[DOC2QUERY] JSON parse error for %s (attempt %d)", cid[:16], attempt + 1)
                except Exception as e:
                    logger.warning("[DOC2QUERY] Error for %s (attempt %d): %s", cid[:16], attempt + 1, e)
                    if attempt == 0:
                        await asyncio.sleep(1)

            return cid, []

    tasks = [process_one(chunk) for chunk in chunks]
    for coro in asyncio.as_completed(tasks):
        cid, queries = await coro
        results[cid] = queries
        if queries:
            print(f"  [{len(results)}/{len(chunks)}] {cid[:16]}: {len(queries)} queries", flush=True)
        else:
            print(f"  [{len(results)}/{len(chunks)}] {cid[:16]}: FAILED", flush=True)

    return results


def store_queries(db_path: Path, queries_by_id: dict[str, list[str]]) -> int:
    """Store generated queries in chunk_meta.generated_queries column."""
    conn = sqlite3.connect(str(db_path))
    stored = 0
    try:
        # Add column if missing
        try:
            conn.execute("SELECT generated_queries FROM chunk_meta LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(
                "ALTER TABLE chunk_meta ADD COLUMN generated_queries TEXT NOT NULL DEFAULT ''"
            )
            logger.info("[DOC2QUERY] Added generated_queries column to chunk_meta")

        for cid, queries in queries_by_id.items():
            if queries:
                conn.execute(
                    "UPDATE chunk_meta SET generated_queries = ? WHERE chunk_id = ?",
                    (json.dumps(queries, ensure_ascii=False), cid),
                )
                stored += 1
        conn.commit()
    finally:
        conn.close()
    return stored


def rebuild_fts_with_queries(db_path: Path) -> int:
    """Rebuild FTS5 index with generated queries appended to title column."""
    conn = sqlite3.connect(str(db_path))
    rebuilt = 0
    try:
        cursor = conn.cursor()

        # Check if generated_queries column exists
        try:
            cursor.execute("SELECT generated_queries FROM chunk_meta LIMIT 1")
        except sqlite3.OperationalError:
            print("No generated_queries column — nothing to rebuild")
            return 0

        # Read all chunks with their queries
        cursor.execute(
            "SELECT chunk_id, section_title, original_content, generated_queries "
            "FROM chunk_meta"
        )
        rows = cursor.fetchall()

        # Clear FTS5
        conn.execute("DELETE FROM chunks_fts")

        for cid, section_title, content, gen_queries_json in rows:
            if not content or not content.strip():
                continue

            # Parse generated queries
            queries = []
            if gen_queries_json:
                try:
                    queries = json.loads(gen_queries_json)
                except json.JSONDecodeError:
                    pass

            # Build enriched title: section_title + generated queries
            title_parts = []
            if section_title:
                title_parts.append(section_title)
            title_parts.extend(queries)
            title_text = "\n".join(title_parts)

            # Lemmatize
            lemma_title = lemmatize_text(title_text) if title_text else ""
            lemma_body = lemmatize_text(content)

            # Get document_id and source
            cursor.execute(
                "SELECT document_id, source FROM chunk_meta WHERE chunk_id = ?", (cid,)
            )
            meta = cursor.fetchone()
            doc_id = meta[0] if meta else ""
            source = meta[1] if meta else ""

            cursor.execute(
                "INSERT INTO chunks_fts (chunk_id, title, body, document_id, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (cid, lemma_title, lemma_body, doc_id, source),
            )
            rebuilt += 1

        conn.commit()
    finally:
        conn.close()
    return rebuilt


async def main():
    limit = None
    rebuild_flag = "--rebuild" in sys.argv
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    settings = get_settings()

    if not settings.anthropic_api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        return

    # Initialize BM25 store
    bm25 = BM25Store(db_path=settings.search.bm25_db_path)
    await bm25.initialize()
    total = await bm25.count()
    print(f"BM25 index: {total} chunks")

    if total == 0:
        print("No chunks in BM25 index. Run build_bm25_index.py first.")
        return

    # Read chunks that need enrichment
    db_path = settings.search.bm25_db_path
    conn = sqlite3.connect(str(db_path))

    # Add column if missing
    try:
        conn.execute("SELECT generated_queries FROM chunk_meta LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute(
            "ALTER TABLE chunk_meta ADD COLUMN generated_queries TEXT NOT NULL DEFAULT ''"
        )
        conn.commit()

    cursor = conn.cursor()
    if limit:
        cursor.execute(
            "SELECT chunk_id, section_title, original_content, generated_queries "
            "FROM chunk_meta WHERE generated_queries = '' LIMIT ?",
            (limit,),
        )
    else:
        cursor.execute(
            "SELECT chunk_id, section_title, original_content, generated_queries "
            "FROM chunk_meta WHERE generated_queries = ''"
        )

    chunks_to_enrich = []
    for row in cursor.fetchall():
        chunks_to_enrich.append({
            "chunk_id": row[0],
            "section_title": row[1] or "",
            "original_content": row[2] or "",
        })
    conn.close()

    print(f"Chunks to enrich: {len(chunks_to_enrich)}")

    if not chunks_to_enrich:
        if rebuild_flag:
            print("\n=== Rebuilding FTS5 with stored queries ===")
            rebuilt = rebuild_fts_with_queries(db_path)
            print(f"Rebuilt FTS5: {rebuilt} chunks")
        else:
            print("All chunks already enriched. Use --rebuild to rebuild FTS5.")
        return

    # Generate queries in batches
    batch_size = 20
    all_queries: dict[str, list[str]] = {}
    t0 = time.time()

    for i in range(0, len(chunks_to_enrich), batch_size):
        batch = chunks_to_enrich[i:i + batch_size]
        print(f"\n=== Batch {i // batch_size + 1} ({len(batch)} chunks) ===")

        batch_queries = await generate_queries_batch(
            chunks=batch,
            api_key=settings.anthropic_api_key,
            base_url=settings.agent.base_url,
            model=settings.agent.reranker_llm_model,  # Sonnet
            concurrency=5,
        )
        all_queries.update(batch_queries)

        # Store incrementally
        stored = store_queries(db_path, batch_queries)
        elapsed = time.time() - t0
        success = sum(1 for q in batch_queries.values() if q)
        print(f"  Stored: {stored}, Success: {success}/{len(batch)}, Time: {elapsed:.1f}s")

    # Summary
    elapsed = time.time() - t0
    success = sum(1 for q in all_queries.values() if q)
    total_queries = sum(len(q) for q in all_queries.values())
    print(f"\n{'='*60}")
    print(f"doc2query enrichment complete:")
    print(f"  Chunks processed: {len(all_queries)}")
    print(f"  Success: {success}/{len(all_queries)}")
    print(f"  Total queries generated: {total_queries}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"{'='*60}")

    # Rebuild FTS5 with queries
    print("\n=== Rebuilding FTS5 with generated queries ===")
    rebuilt = rebuild_fts_with_queries(db_path)
    print(f"Rebuilt FTS5: {rebuilt} chunks (queries in title column with 10x boost)")


if __name__ == "__main__":
    asyncio.run(main())
