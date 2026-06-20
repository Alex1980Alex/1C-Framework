# 02 — Дизайн (approved)

Решение — [ADR-026](../../.claude/skills/architecture-research/adr/026-state-first-1c-pipeline-enforcement.md).

Усиление = **advisory** PreToolUse `onec-state-first-guard` (паттерн `tdd-guard`): `Write|Edit|MultiEdit` файла `.bsl/.mdo/.form` под `configuration/`/`ИБTransport` БЕЗ активного 1С-pipeline-state (`title "1С-задача (" ∧ current_stage<5`) → system_message-нудж «войди через /run-1c-task / заведи state». **Никогда не блок**; opt-out `ONEC_STATE_FIRST_DISABLE=1`; graceful; регистрация в `settings.local.json` (как tdd-guard, team не тронут).

Альтернативы (откл.): hard-block (deadlock, §0.6), только Stop-gate (поздно), сразу team settings.json (cautious rollout).
