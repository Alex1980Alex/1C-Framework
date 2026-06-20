# 03 — Реализация

- [`scripts/check_submodule_push_order.py`](../../scripts/check_submodule_push_order.py) — хелпер: `_submodule_paths` (.gitmodules) / `_gitlink_sha` (ls-tree 160000) / `_is_initialized` / `_on_remote` (`branch -r --contains`) + `main`. Best-effort, exit 1 только при позитивной находке.
- [`scripts/git_hooks/pre-push`](../../scripts/git_hooks/pre-push) — добавлен вызов хелпера в цикле per-ref (после вычисления `base`, `exit 1` при блоке).
- [`tests/unit/test_check_submodule_push_order.py`](../../tests/unit/test_check_submodule_push_order.py) — 5 unit (block / allow-on-remote / unchanged / not-initialized / noop).
- [ADR-027](../../.claude/skills/architecture-research/adr/027-prepush-submodule-ordering-guard.md) + `adr/_index.json`.
