---
unified_id: 019f8a3b-5c7d-7e2a-9f1b-4d6e8a0c2b4f
status: active
tags: [meta, schema, standards, documentation]
related: [[_index]], [[overview]], [[triad-architecture]]
created_at: 2026-04-20T10:00:00Z
updated_at: 2026-04-20T10:00:00Z
confidence: 1.0
---

# Wiki Schema & Standards

Canonical structure, naming conventions, cross-referencing syntax, and lifecycle rules for the PDF Vector & Graph Framework Knowledge Base.

## Memory Model

5-layer retrieval architecture:

| Layer | Storage | Content | Weight |
|-------|---------|---------|--------|
| **L1** | SQLite (`memory_ai.db`) | Session summaries, volatile context | 0.30 |
| **L2** | Qdrant Vectors | Learned patterns, skills, experiences | 0.35 |
| **L3** | Wiki Pages (`docs/wiki/`) | Promoted high-confidence knowledge | 0.20 |
| **L4** | User Memory (`.md` files) | Claude Code `MEMORY.md` | 0.15 |
| **L5** | Wiki Drafts (`docs/wiki/drafts/`) | Pending promotion candidate pages | 0.20* |

*\*L5 shares retrieval weight with L3 during active sessions.*

---

## YAML Frontmatter Schema

Every wiki page must include:

```yaml
---
unified_id: <UUID v7>
status: draft | active | archived
tags:
  - <tag-one>
related:
  - <[[wiki-link]]>
created_at: <ISO 8601 datetime>
updated_at: <ISO 8601 datetime>
confidence: <0.0 to 1.0>
promoted_from: <optional L2 pattern ID>
---
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `unified_id` | UUID v7 | Yes | Unique identifier, time-sortable |
| `status` | Enum | Yes | One of: `draft`, `active`, `archived` |
| `tags` | List | Yes | Categorization tags. Minimum 1, recommended 3-5 |
| `related` | List | Yes | Bidirectional wiki-links |
| `created_at` | ISO 8601 | Yes | Creation timestamp with timezone |
| `updated_at` | ISO 8601 | Yes | Last modification timestamp |
| `confidence` | Float | Yes | Range `0.0` to `1.0` |
| `promoted_from` | String | No | Source L2 pattern ID if promoted from vector store |

---

## Naming Rules

1. **Format:** `lowercase-kebab-case.md`
2. **Maximum length:** 80 characters (excluding `.md`)
3. **Allowed:** lowercase letters (`a-z`), digits (`0-9`), hyphens (`-`)
4. **Prohibited:** spaces, underscores, special characters, uppercase
5. **No consecutive hyphens**

---

## Cross-Reference Rules

### Wiki-Link Syntax

Use double bracket notation: `[[page-name]]`

### Bidirectional Linking

1. When Page A links to Page B, Page B must include Page A in `related`
2. `_index.md` serves as central link registry
3. Maximum **10 related links per page**

---

## Promotion Rules (L2 → L3)

| Criterion | Threshold |
|-----------|-----------|
| Confidence | `>= 0.8` |
| Usage Count | `>= 5` |
| Dedup Cosine Similarity | `< 0.85` |

### Promotion Process

1. **Evaluate:** Check L2 patterns meeting thresholds
2. **Dedup:** Reject if `cosine_similarity(candidate, existing) >= 0.85`
3. **Draft:** Generate in `docs/wiki/drafts/` with `status: draft`
4. **Review:** Manual or automated review
5. **Promote:** Move to `docs/wiki/` with `status: active`
6. **Index:** Add entry to `_index.md`
7. **Backlink:** Update `related` fields on connected pages

---

## Archival Rules

Archive path: `docs/wiki/archive/YYYY-MM/<page-name>.md`

| State | Duration | Action After |
|-------|----------|--------------|
| Archived | 90 days | Permanent deletion |
| Referenced by active page | Until ref removed | 90-day clock starts on removal |

---

## New Page Template

```yaml
---
unified_id: 
status: draft
tags:
  - 
related:
  - 
created_at: 
updated_at: 
confidence: 0.5
promoted_from: 
---

# [Page Title]

## Summary

[One to two sentence summary.]

## Details

[Primary content.]

## See Also

- [[]]
```

---

## Validation Checklist

- [ ] Filename: lowercase-kebab-case, max 80 chars
- [ ] All frontmatter fields present
- [ ] `unified_id` is valid UUID v7
- [ ] `confidence` between 0.0 and 1.0
- [ ] Max 10 items in `related`
- [ ] All `[[wiki-links]]` resolve to existing pages
- [ ] Backlinks added to referenced pages
- [ ] `_index.md` updated
- [ ] No content duplication (cosine < 0.85)
