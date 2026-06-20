# 02 — Дизайн (approved)

Решение — [ADR-027](../../.claude/skills/architecture-research/adr/027-prepush-submodule-ordering-guard.md). **Prevention**, не saga-compensation.

Хелпер `scripts/check_submodule_push_order.py`, вызываемый из `pre-push` с `(base, local_sha)`: детект изменённых gitlink (`git ls-tree`, mode 160000) + проверка достижимости нового sha на remote сабмодуля (`git -C <sub> branch -r --contains`). Не на remote → exit 1 (блок + инструкция). Bypass `PREPUSH_SKIP=1`/`--no-verify`; graceful (возврат 1 ТОЛЬКО при позитивной находке непушенного gitlink'а).

Альтернативы (откл.): saga-движок (over-engineering single-user), `ls-remote` (сетевой, медленно), post-fact revert (реактивно).
