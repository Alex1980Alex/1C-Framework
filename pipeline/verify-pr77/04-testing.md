# 04 — Тест

## T2 — .gitmodules (PASS)
- `git submodule status` → **exit 0**, stderr пуст (раньше падал
  `fatal: no submodule mapping found` сначала на tree-sitter, затем на multilspy).
- Обе строки присутствуют: `-2bc0435d… tools/bsl-ls/tree-sitter-bsl-src`,
  `-f2a570287… tools/multilspy-fork` (префикс `-` = не инициализирован в этом клоне,
  но маппинг распознан — корректно).
- URL'ы резолвятся в форки с ветками, реально содержащими пиннутые SHA
  (`branch -r --contains` подтвердил: upstream НЕ содержит).

## Верификация PR #77 (PASS) — re-confirm
Вердикт стоит; правка T2 ничего из проверенного не затрагивает (отдельный файл).

## T1 / T4 — будут протестированы после исполнения
- T1: `gh pr view 77` показывает обновлённое тело без устаревших SHA.
- T4: критерий зависит от выбранной опции (узкий PR собирается / ре-тайтл виден).

## Findings из верификации (для трекинга)
- ⚠ дифф 162 файла ≫ описания PR (T1/T4 адресуют).
- ⚠ SHA сабмодулей в теле устарели (T1 адресует).
- ✅ stray-gitlink'и без маппинга (T2 — исправлено).
- env: cold-start 7.82s вместо ~510s (стек прогрет); death-spiral в этой среде не
  воспроизводим, `asyncio.shield`-половина проверена по коду.

## Integration-suite remediation (PASS) — каскад «исправь все reds»

Верификация выявила BLOCKER (`memory_ttl_cleanup` `len(int)` TypeError — исправлен
коммитом 943a37f0a + регресс) и дрейф интеграционного набора (57 passed / 22 failed,
non-gating). Полная ремедиация выполнена пер-кластерно, каждый — отдельным PR,
master CI зелёный на всём протяжении:

- **PR #82** test_search — 8 тестов (внешняя проводка стратегий через `register_strategy`).
- **PR #83** test_api — 6 pass / 2 accurate-skip (`app.dependency_overrides[get_components]`).
- **PR #84** test_plan_execute — 14 тестов + **source-bug** `run_plan_execute` (dict-vs-attr).
- **PR #85** test_visual (+2) / test_proposition (+1, **source-bug** async metadata
  `original_chunk_id`) / test_post_commit (+1) / test_pdf_docs (+1).

Итог: все кластеры закрыты; оставшиеся skip — легитимные service/dep-гейты (multilspy,
LLM-chain ask/chat, live-TEI, mock_vector_store, git-hooks-path). 2 продовых бага
исправлены попутно. code-verify PASS (subagent afa6295ff0b358b9f). Детали + таблица
root-cause: [docs/roadmap/260614](../../docs/roadmap/260614_ROADMAP_INTEGRATION_TEST_REMEDIATION.md).
