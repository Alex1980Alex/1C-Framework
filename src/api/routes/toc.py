"""Table of Contents API (Phase 30).

REST endpoints for navigating document structure:
- GET /toc/{document_id} — full ToC tree
- GET /toc/{document_id}/section/{section_number} — section detail
- POST /toc/{document_id}/generate-summaries — trigger LLM summaries
"""

import re
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.components import Components, get_components

router = APIRouter(prefix="/toc", tags=["toc"])


def _build_toc_tree(chunks: list[Any]) -> list[dict[str, Any]]:
    """Build a ToC tree from chunk metadata.

    Groups chunks by section_number, then builds a nested tree
    from the hierarchical numbering (e.g. 5 > 5.1 > 5.1.2).
    """
    # Collect unique sections with metadata
    sections: dict[str, dict[str, Any]] = {}

    for chunk in chunks:
        meta = chunk.metadata if hasattr(chunk, "metadata") else {}
        section_num = meta.get("section_number", "")

        # Fallback: extract section_number from section_title (e.g. "**5.8.Справочники**")
        if (not section_num or section_num == "None") and meta.get("section_title"):
            raw_title = meta["section_title"].strip().strip("*")
            m = re.match(r"(\d+(?:\.\d+)*)", raw_title)
            if m:
                section_num = m.group(1)

        if not section_num or section_num == "None":
            continue

        if section_num not in sections:
            breadcrumb = meta.get("breadcrumb", "")
            # Extract title from breadcrumb or section_title
            section_title = ""
            if breadcrumb:
                last_part = breadcrumb.rsplit(" > ", 1)[-1] if " > " in breadcrumb else breadcrumb
                # Remove leading number: "5.1.2. Title" → "Title"
                title_match = re.match(r"\d+(?:\.\d+)*\.?\s*(.*)", last_part)
                section_title = title_match.group(1) if title_match else last_part
            elif meta.get("section_title"):
                # Strip bold markdown and leading number
                raw = meta["section_title"].strip().strip("*")
                title_match = re.match(r"\d+(?:\.\d+)*\.?\s*(.*)", raw)
                section_title = title_match.group(1) if title_match else raw

            sections[section_num] = {
                "number": section_num,
                "title": section_title,
                "breadcrumb": breadcrumb,
                "chunk_count": 0,
                "page_start": None,
                "page_end": None,
                "level": section_num.count(".") + 1,
            }

        sec = sections[section_num]
        sec["chunk_count"] += 1

        page = meta.get("page_number") or meta.get("page")
        if page:
            page_int = int(page) if isinstance(page, str) and page.isdigit() else page
            if isinstance(page_int, int):
                if sec["page_start"] is None or page_int < sec["page_start"]:
                    sec["page_start"] = page_int
                if sec["page_end"] is None or page_int > sec["page_end"]:
                    sec["page_end"] = page_int

    if not sections:
        return []

    # Sort by section number (natural order)
    sorted_sections = sorted(
        sections.values(),
        key=lambda s: [int(x) for x in s["number"].split(".") if x.isdigit()],
    )

    # Build tree: group children under parents
    # A section 5.1.2 is a child of 5.1, which is a child of 5
    root_nodes: list[dict[str, Any]] = []
    node_map: dict[str, dict[str, Any]] = {}

    for sec in sorted_sections:
        node = {**sec, "children": []}
        node_map[sec["number"]] = node

        # Find parent: 5.1.2 → parent is 5.1
        parts = sec["number"].split(".")
        parent_num = ".".join(parts[:-1]) if len(parts) > 1 else ""

        if parent_num and parent_num in node_map:
            node_map[parent_num]["children"].append(node)
        else:
            root_nodes.append(node)

    return root_nodes


@router.get("/{document_id}")
async def get_document_toc(
    document_id: str,
    components: Components = Depends(get_components),
):
    """Get document table of contents as tree.

    Builds ToC from chunk metadata (section_number, breadcrumb).
    Returns nested tree structure with chunk counts and page ranges.
    """
    # Scroll all chunks for this document
    chunks = await components.vector_store.scroll(
        filter={"document_id": document_id},
        limit=5000,
    )

    if not chunks:
        raise HTTPException(status_code=404, detail=f"No chunks found for document {document_id}")

    tree = _build_toc_tree(chunks)

    # Get summary count if service available
    summary_count = 0
    if components.section_summary:
        summaries = await components.section_summary.get_all(document_id)
        summary_count = len(summaries)

    return {
        "document_id": document_id,
        "total_chunks": len(chunks),
        "total_sections": _count_sections(tree),
        "summaries_available": summary_count,
        "tree": tree,
    }


@router.get("/{document_id}/section/{section_number:path}")
async def get_section_detail(
    document_id: str,
    section_number: str,
    components: Components = Depends(get_components),
):
    """Get detailed info about a specific section.

    Returns: breadcrumb, chunk count, page range, summary (if available),
    and list of child sections.
    """
    # Find all chunks in this section
    all_chunks = await components.vector_store.scroll(
        filter={"document_id": document_id},
        limit=5000,
    )

    section_chunks = []
    for c in all_chunks:
        meta = c.metadata or {}
        sn = meta.get("section_number", "")
        # Fallback: extract from section_title
        if (not sn or sn == "None") and meta.get("section_title"):
            raw = meta["section_title"].strip().strip("*")
            m = re.match(r"(\d+(?:\.\d+)*)", raw)
            if m:
                sn = m.group(1)
        if sn and sn.startswith(section_number):
            section_chunks.append(c)

    if not section_chunks:
        raise HTTPException(
            status_code=404,
            detail=f"Section {section_number} not found in document {document_id}",
        )

    # Build mini-tree for this section
    tree = _build_toc_tree(section_chunks)

    # Get summary if available
    summary = None
    if components.section_summary:
        summary = await components.section_summary.get_summary(document_id, section_number)

    # Compute page range
    pages = set()
    for c in section_chunks:
        page = (c.metadata or {}).get("page_number") or (c.metadata or {}).get("page")
        if page:
            try:
                pages.add(int(page))
            except (ValueError, TypeError):
                pass

    # Get breadcrumb from first matching chunk
    breadcrumb = ""
    for c in section_chunks:
        bc = (c.metadata or {}).get("breadcrumb", "")
        if bc:
            breadcrumb = bc
            break

    return {
        "document_id": document_id,
        "section_number": section_number,
        "breadcrumb": breadcrumb,
        "chunk_count": len(section_chunks),
        "page_start": min(pages) if pages else None,
        "page_end": max(pages) if pages else None,
        "summary": summary,
        "children": tree,
    }


@router.post("/{document_id}/generate-summaries")
async def generate_section_summaries(
    document_id: str,
    components: Components = Depends(get_components),
):
    """Trigger LLM summary generation for all sections of a document.

    Reads chunks from vector store, extracts sections, and generates
    2-3 sentence summaries for each section. Results are cached in SQLite.
    """
    if not components.section_summary:
        raise HTTPException(
            status_code=501,
            detail="Section summary service is not enabled (set HIERARCHICAL__SUMMARY_ENABLED=true)",
        )

    # Read all chunks
    chunks = await components.vector_store.scroll(
        filter={"document_id": document_id},
        limit=5000,
    )

    if not chunks:
        raise HTTPException(status_code=404, detail=f"No chunks found for document {document_id}")

    # Extract unique sections
    sections_map: dict[str, str] = {}
    for chunk in chunks:
        meta = chunk.metadata or {}
        section_num = meta.get("section_number", "")
        # Fallback: extract from section_title
        if (not section_num or section_num == "None") and meta.get("section_title"):
            raw = meta["section_title"].strip().strip("*")
            m = re.match(r"(\d+(?:\.\d+)*)", raw)
            if m:
                section_num = m.group(1)
        if not section_num or section_num == "None":
            continue
        if section_num not in sections_map:
            breadcrumb = meta.get("breadcrumb", "")
            title = ""
            if breadcrumb:
                last_part = breadcrumb.rsplit(" > ", 1)[-1] if " > " in breadcrumb else breadcrumb
                title_match = re.match(r"\d+(?:\.\d+)*\.?\s*(.*)", last_part)
                title = title_match.group(1) if title_match else last_part
            sections_map[section_num] = title

    sections = [
        {"number": num, "title": title}
        for num, title in sorted(sections_map.items())
    ]

    # Convert chunks to dicts for summary service
    chunk_dicts = [
        {
            "content": c.content,
            "metadata": c.metadata or {},
        }
        for c in chunks
    ]

    generated = await components.section_summary.generate_for_document(
        document_id=document_id,
        chunks=chunk_dicts,
        sections=sections,
    )

    all_summaries = await components.section_summary.get_all(document_id)

    return {
        "document_id": document_id,
        "sections_found": len(sections),
        "summaries_generated": generated,
        "total_summaries": len(all_summaries),
        "summaries": all_summaries,
    }


def _count_sections(tree: list[dict]) -> int:
    """Count total sections in a tree (recursive)."""
    count = 0
    for node in tree:
        count += 1
        count += _count_sections(node.get("children", []))
    return count
