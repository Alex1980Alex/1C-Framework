# 02 — Дизайн: подход по каждому follow-up

## T2 — .gitmodules (ВЫПОЛНЕНО)
Оба stray-gitlink'а смапплены. Ключевой нюанс: пиннутые SHA лежат **только в форках
`Alex1980Alex/*`**, не в upstream (alkoleft/microsoft) — проверено
`git -C <sub> branch -r --contains <sha>`. Поэтому URL = форк + ветка с коммитом:
- `tools/bsl-ls/tree-sitter-bsl-src` → `Alex1980Alex/tree-sitter-bsl` @ `fix/parenthesized-expression`
- `tools/multilspy-fork` → `Alex1980Alex/multilspy` @ `feat/bsl-language`
Критерий приёмки: `git submodule status` exit 0 без `no submodule mapping`.

## T1 — тело PR #77
Переписать `gh pr edit 77 --body-file`: (а) честно описать, что ветка несёт весь
накопленный объём (pipeline ADR-017/018, skill-router eval, tdd-guard, memory,
десятки хуков), не только ремедиацию+2 райдера; (б) НЕ хардкодить churn-prone SHA
сабмодулей — описать обобщённо («бамп до текущих heads/master конфиг-сабмодулей»);
(в) сохранить раздел Verification. Обратимо. Выполняется ПОСЛЕ решения по T4
(тело зависит от итогового scope).

## T4 — scope (GATE на одобрение, force-push)
Опции:
- **A (рекомендую). Честный ре-тайтл + тело, без переписывания истории.** Дёшево,
  безопасно, не трогает 48-коммитную историю. PR честно становится «бандлом ветки».
- **B. Истинный split.** Cherry-pick remediation+2 райдера на свежую ветку от
  `master` → отдельный узкий PR; большой хвост — свой (ре-тайтл) PR. Чисто, но
  коммиты переплетены с auto-save за недели → трудоёмко/риск ошибки.
- **C. Полный interactive rebase** (drop/reorder/squash хвоста). Макс. чистота,
  макс. риск; force-push обязателен. Не рекомендую.
Все, кроме «только тело», требуют force-push → одобрение пользователя.

## ADR
Новый ADR не нужен: это process/hygiene, не архитектурное решение фреймворка.
