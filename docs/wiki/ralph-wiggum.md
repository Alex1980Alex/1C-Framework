---
confidence: 0.3
related:
- '[[_index]]'
status: draft
tags:
- automation
- verification
- pattern
title: Ralph Wiggum Loop
unified_id: 019e1e30-10a9-7e72-be5d-c769a631589c
---

Iterative retry pattern used by `code-verify` and learning-loop: on FAIL, feed reviewer feedback back to the fixer
agent, retry up to 3 times. See `.claude/skills/code-verify/SKILL.md` for the canonical 4-mode pipeline.

## Loop semantics

Each iteration receives: reference + previous attempt + reviewer feedback + instruction "fix ONLY the listed issues".
After 3 unsuccessful iterations — stop, explain root cause, mark as "requires manual review".

**Status: stub.** Expand with example transcripts.
