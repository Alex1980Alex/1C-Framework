# 02 — Дизайн (approved)

- **C1:** отдельное значение `flow="ask_action"` (actionless) — enum самодостаточен, потребителю не нужен доп-ключ.
- **C4:** `veto_immune = confidence ≥ 0.9` (JIRA/код/гкс_/configuration); CamelCase 0.7 → veto-able (`non_1c_ctx = (not veto_immune) and …`).
- **C2/C3:** новый helper `resolve_active_1c_slug(prompt)` (JIRA-код → иначе CURRENT-если-1С); `gate_1c_implement` + `ensure_pipeline_1c(implement)` на нём → единая идентификация; `/implement` прицепляется к пайплайну `/analyze` через CURRENT для не-JIRA.

Порядок: low→high risk (C1 → C4 → C2/C3), каждый шаг — коммит + verify. C2/C3 — code-verify reviewer (архитектурный).
