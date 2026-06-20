# 01 — Планирование

**Задача:** усиление пайплайна 1С — чтобы 1С-работа шла **state-first** (через машинерию), а не задним числом.
**Источник:** ретро GKSTCPLK-2521 — 4 отклонения (state заведён на Stop; методики обойдены; петли recall/research/capture под принуждением; G4 неформален).
**Цель:** (A) алгоритм «1С строго по пайплайну» (память + 43.5) + (B) PreToolUse-хук, напоминающий на ПЕРВОЙ 1С-правке без активного pipeline-state (gate-at-creation).
**Research:** [cache/agentic-pipeline-workflow-enforcement-2026](../../.claude/skills/architecture-research/cache/agentic-pipeline-workflow-enforcement-2026.md) — Spec Kit/Kiro/BMAD/LangGraph/guardrails.
