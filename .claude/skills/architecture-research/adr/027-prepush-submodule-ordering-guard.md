# ADR-027: pre-push submodule-ordering guard (защита от dangling gitlink, класс PR #77)

**Дата:** 2026-06-20
**Статус:** accepted
**Исследование:** [../cache/orchestration-best-practices.md](../cache/orchestration-best-practices.md) (паттерн #11 Saga/compensation; прод-практика #11 dead-letter/compensation-on-failure)

## Контекст

Критический анализ оркестрации (cache `orchestration-best-practices`, 19 фреймворков + 17 паттернов + 12 прод-практик) под наш **single-user** контекст выявил единственный gap с конкретной непокрытой ценностью: **партиал-эффект при multi-repo push**.

Класс PR #77 ([[project-embedded-git-repos]]): родитель пушит gitlink сабмодуля на коммит, НЕ запушенный в remote сабмодуля → на remote **dangling gitlink** (клон/CI ломается). Проверено в коде: [`scripts/git_hooks/pre-push`](../../../../scripts/git_hooks/pre-push) гейтит только `ruff+compileall` по `.py`; [`submodule-status-check.py`](../../../hooks/submodule-status-check.py) ловит *незакоммиченные* правки сабмодулей — **push-ordering «сабмодуль → родитель» не покрыт ничем**.

Saga/compensation из кеша — про *откат* side-effects (compensation); здесь дешевле **prevention** (не дать опубликовать партиал), а не движок отката.

## Решение

Расширить [`scripts/git_hooks/pre-push`](../../../../scripts/git_hooks/pre-push) вызовом хелпера [`scripts/check_submodule_push_order.py`](../../../../scripts/check_submodule_push_order.py): для каждого пушимого ref'а родителя найти изменённые gitlink'и сабмодулей в `base..local` (`git ls-tree`, mode 160000) и для каждого нового sha проверить достижимость на remote сабмодуля (`git -C <sub> branch -r --contains <sha>`). Не на remote → **блок push** с инструкцией «сначала запушь сабмодуль». Bypass: `PREPUSH_SKIP=1` / `git push --no-verify`. Graceful: ошибка/неинициализированный сабмодуль → пропуск (exit 0) — guard не ломает легальный push (возвращает 1 ТОЛЬКО при позитивно найденном непушенном gitlink'е).

## Последствия

### Положительные
- Класс PR #77 предотвращается на **границе публикации** (gate-at-publish — продолжение линии ADR-026 «state-first / guards на границе»).
- Малый, обратимый (1 хелпер + ~6 строк в `pre-push`), в существующей идиоме pre-push; покрыт 5 unit-тестами.

### Отрицательные / риски
- `branch -r --contains` опирается на remote-tracking refs (после `push` сабмодуля обновляются локально); экзотический push без обновления tracking → возможен ложный блок (есть bypass).
- +1 git-вызов на сабмодуль при push родителя (push нечаст — приемлемо).

## Альтернативы
- **Saga-движок / compensation-стадия** — отклонено: over-engineering для single-user; нужен prevention, не откат.
- **`git ls-remote` проверка** — точнее, но сетевой вызов на каждый push (медленно); `branch -r --contains` достаточно (idiom auto-save amend).
- **Post-fact авто-revert** (post-merge revert класс) — реактивно; prevention дешевле и раньше.

## Связанные файлы
- [`scripts/check_submodule_push_order.py`](../../../../scripts/check_submodule_push_order.py) · [`scripts/git_hooks/pre-push`](../../../../scripts/git_hooks/pre-push) · [`tests/unit/test_check_submodule_push_order.py`](../../../../tests/unit/test_check_submodule_push_order.py)
- research — [cache/orchestration-best-practices.md](../cache/orchestration-best-practices.md); линия решений — ADR-026 (state-first guards).
