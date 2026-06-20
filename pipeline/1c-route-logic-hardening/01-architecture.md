# 01 — Планирование

Hardening логики маршрутизации 1С ([`pipeline_1c_bridge.py`](../../.claude/hooks/shared/pipeline_1c_bridge.py)) — findings C1-C4 из аудита 43.5.

- **C1:** `flow=ask_flow` перегружен двумя смыслами (medium «AUTO/гейт?» + actionless «что сделать?»), различим лишь доп-ключом `actionless`.
- **C2/C3:** G4 ненадёжен для не-JIRA — `gate_1c_implement` искал по `derive_slug(prompt)`, а `advance_*`/preflight — по `resolve_current()` → расходятся (analyze-slug ≠ implement-slug) → no-op либо ложный блок.
- **C4:** CamelCase-кириллица (confidence 0.7) → confident → обходит non-1C veto (immune как JIRA/гкс_).
