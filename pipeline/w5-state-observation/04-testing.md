# W5′ — тестирование

## Unit (584 total, +51 W5′)
- `test_c4_watchpoint.py` — 19: match_predicate/parse_break_when/plan/read_timeline(+run_id filter) + fire/compare (record_only/unchanged/break_on_first_change/break_when±/cap/no-match).
- `test_c6_counts_seek.py` — 10: counts sidecar (top-N, zero-only), parse_seek_query (longest-op, nameless-reject), match_entry (var/special/bool/CI/missing), seek_by_query first-match.
- `test_a6_session_state.py` — 11: 5 состояний + exception-приоритет, state_hint shape/valid_next, correlation persist/restore.
- `test_a4_diff_runs.py` — 12: hit_index, align union-order, flow>state, longer-run, ignore, CI-lookup, state_diffs cap/present.

Прогон: `python -m pytest tests/ -q` → **584 passed**. Регрессий нет (было 533 до W5′).

## Code-verify
Read-only reviewer (quality-review+behavior-preservation), subagent `a4043b295bd32a196` → **PASS**. 2 non-blocking рекомендации применены:
1. `read_timeline` фильтрует по `run_id` (гонка late-write прежнего run при re-arm) + регресс-тест.
2. `_last_visible_stop_ts` выставляется на halt-promote watchpoint (M-6 age-bound parity).
Rec 3 (pre-existing `list_snapshots` stack[0] vs stack[-1]) — вне scope W5′.

## Live-harness (held-JOB B1)
НЕ блокирующий: W5′ не вводит новых RDBG wire-семантик — C4 = plain BP + eval + Continue (все live-validated в W1/W3), C6/A6/A4 = чистый Python над записанными артефактами. Live-прогон (`debug_set_watchpoint`→held-JOB→3 присваивания; `debug_diff_runs` два записанных прогона) доступен on-demand при поднятом dbgs; отличие от B1/C1 — там зондировались новые команды (`modifyValue`, held-worker), здесь нет. Требует `/mcp reconnect` (новые tools + изменённые схемы `debug_replay_seek`/`debug_session_record`/`debug_connect`).
