"""Classify GitHub notification reason+subject → category + priority."""

from __future__ import annotations

import re

# Order matters: first-match-wins. CI failures take precedence over source —
# "Dependabot workflow run failed" → ci-fail/P1, not dependabot/P2.
CATEGORIES = {
    "ci-fail": (re.compile(r"workflow run failed|All jobs have failed|Run failed", re.I), "P1"),
    "security": (re.compile(r"security advisory|vulnerab|CodeQL", re.I), "P0"),
    "pr-review": (
        re.compile(r"commented on|approved|requested changes|review_requested", re.I),
        "P1",
    ),
    "merged": (re.compile(r"merged|pull request closed", re.I), "P3"),
    # Catches "Bump X from A to B" Dependabot PR titles + "update X requirement"
    "dependabot": (
        re.compile(r"dependabot|update .* requirement|^bump\s.*\sfrom\s.*\sto\s", re.I),
        "P2",
    ),
}


def classify(subject: str, reason: str = "") -> tuple[str, str]:
    text = f"{subject} {reason}"
    for category, (pattern, priority) in CATEGORIES.items():
        if pattern.search(text):
            return category, priority
    return "other", "P3"


def summarize(notifications: list[dict]) -> dict:
    counts: dict = {}
    priorities: dict = {}
    for n in notifications:
        cat, prio = classify(n.get("subject", ""), n.get("reason", ""))
        counts[cat] = counts.get(cat, 0) + 1
        priorities[prio] = priorities.get(prio, 0) + 1
    return {"total": len(notifications), "by_category": counts, "by_priority": priorities}
