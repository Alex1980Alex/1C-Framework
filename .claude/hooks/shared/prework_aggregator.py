"""Pre-Work result aggregator (ADR-D2).

Merges results from N prework workers → top-K systemMessage injection.
Per ADR-D2 §17.2: cap ≤500 tokens для one-hook MVP; full MMR + adaptive
routing будет в P1 при добавлении ≥2 workers.

References:
- ADR-D2: roadmap 260523 §17.2
- Cache: tech-research/cache/rag-token-budget-adaptive-injection-2026.md
"""

from __future__ import annotations

from typing import Any

MAX_TOTAL_CHARS = 2000  # ~500 tokens approximation (4 chars/token avg)
MAX_ITEMS_PER_SOURCE = 3
MAX_ITEM_CHARS = 200


def _truncate(text: str, limit: int) -> str:
    """Trim to limit, append … if cut."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_system_message(results: list[dict[str, Any]]) -> str:
    """Build flat systemMessage from prework results.

    Args:
        results: list of {label, items, error?} dicts from dispatch_all().
                 Each item should be dict с keys: title, body, score (optional).

    Returns:
        Markdown systemMessage string или "" if no useful content.
    """
    sections: list[str] = []
    total_chars = 0
    errors: list[str] = []

    for result in results:
        label = result.get("label", "?")
        error = result.get("error")
        if error:
            errors.append(f"[{label}] {error}")
            continue

        items = result.get("items", [])
        if not items:
            continue

        # Sort by score desc если есть; иначе stable order
        items_sorted = sorted(
            items,
            key=lambda x: x.get("score", 0.0) if isinstance(x, dict) else 0.0,
            reverse=True,
        )

        lines = [f"**[{label}]**"]
        for item in items_sorted[:MAX_ITEMS_PER_SOURCE]:
            if isinstance(item, dict):
                title = item.get("title", "?")
                body = item.get("body", "")
                entry = f"- {title}"
                if body:
                    entry += f" — {_truncate(body, MAX_ITEM_CHARS)}"
            else:
                entry = f"- {_truncate(str(item), MAX_ITEM_CHARS)}"

            if total_chars + len(entry) > MAX_TOTAL_CHARS:
                lines.append("- …(truncated)")
                break
            lines.append(entry)
            total_chars += len(entry)

        if len(lines) > 1:  # has at least 1 item beyond header
            sections.append("\n".join(lines))

    if not sections and not errors:
        return ""

    parts: list[str] = []
    if sections:
        parts.append("[PREWORK CONTEXT]")
        parts.extend(sections)
    if errors:
        # Errors silent — log в audit log, не показываем Claude
        # (можно add к sections если будет полезно для debugging)
        pass

    return "\n\n".join(parts)
