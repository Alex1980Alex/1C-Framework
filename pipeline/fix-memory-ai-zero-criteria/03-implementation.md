# 03 — Реализация

## Правки

| # | Файл | Что |
|---|---|---|
| 1 | [`session-memory-save.py`](../../.claude/hooks/session-memory-save.py) | `already_saved` → возвращает инкумбента `{content_hash, reason}` вместо bool; путь дедупа эмитит `_record_ingest("dup", …)`; `_record_ingest(**kw)` |
| 2 | [`shared/reflection.py`](../../.claude/hooks/shared/reflection.py) | `DEFAULT_MIN_CLUSTER` 3→2; `_record_links` в `on_created` **и** `on_present`; `harvester="reflection"`; фикс fallback-импорта |
| 3 | [`shared/pattern_harvest.py`](../../.claude/hooks/shared/pattern_harvest.py) | новый колбэк `on_present(item, pid)` в `ingest_items` + вызов на dup-ветке |
| 4 | [`reflect_memory.py`](../../scripts/reflect_memory.py) | выделен `_build_parser()`; дефолты из констант модуля |
| 5 | [`memory_maintenance.py`](../../scripts/memory_maintenance.py) | `_job_apply()` + `_applied_jobs()`; проводка в `_run_subprocess`; честная отчётность |
| 6 | [`memory_ai_acceptance.py`](../../scripts/memory_ai_acceptance.py) | `_reflection_clusters_triggered()`, `_reflection_wrote()`; критерий 5 → пара 5+6 |
| 7 | [`memory-ai-acceptance-on-start.py`](../../.claude/hooks/memory-ai-acceptance-on-start.py) | `_progress` под новые ключи |
| 8 | `.claude/settings.local.json` | `MEMORY_MAINTENANCE_APPLY_REFLECT=1` |

## Отклонения от 02-design.md

**Четвёртые ворота (не были в дизайне).** Живой `--apply` дал `created=0 skipped_dup=2`
→ 0 рёбер. Причина: `ingest_items` на dup-ветке делал `continue` **до** `on_created`.
Провенанс терялся навсегда для любой точки, до которой другой харвестер добрался
первым, и ни один повторный прогон её не бэкфиллил. Дизайн предполагал 3 ворот —
их оказалось 4. Решение (`on_present`) аддитивно: второй потребитель (`harvest`)
параметр не передаёт, дефолт `None`.

**Латентный баг fallback-импорта.** `reflection.py` грузил `pattern_harvest` по
файловому пути, не регистрируя в `sys.modules` до `exec_module` → `@dataclass`
(pattern_harvest.py:136) читает `sys.modules[cls.__module__]` во время исполнения тела
класса → `None.__dict__` → AttributeError. Помечен `# pragma: no cover` и потому
никогда не исполнялся: сломан с рождения. Мой acceptance-модуль стал первым, кто в
него попал.

**Коллизия `shared`.** Первая редакция `_reflection_clusters_triggered` делала
`sys.path.append(hooks_dir)`, но модуль держит `src` в `sys.path[0]` → `shared`
резолвился в `src/shared` → ImportError → проглочен → тихий 0. Ровно
[[feedback-hook-src-shared-collision]]. Итог: загрузка по файловому пути.

## Правки по адверсариальному ревью (вердикт PARTIAL → фиксы)

Ревьюер (`ab2c7aaf`) разобрал 14 находок. Существенные:

- **№1 (принято, я был неправ).** Первая редакция пары критериев **не наблюдала путь
  записи**: `reflection_reachable` считается по корпусу и не зависит от того, запускался
  ли джоб; `reflection_linked` вечно-зелёный на рёбрах от 06-11. Флаг живёт в gitignored
  `settings.local.json` → клон/другая машина/удалённая строка = молчаливый возврат в
  dry-run при зелёном вердикте. Замена: `reflection_linked` → **`reflection_wrote`**
  (ingest-событие `harvester=reflection`; эмитится только при `not dry_run`).
  Заодно снят мой ложный тезис в docstring: старый критерий **не** «проспал» баг —
  он горел красным, просто не отличал «сломано» от «нечего делать».
- **№3.** Эмитился хеш **отвергнутого кандидата**: `format_summary(ctx)` пересчитывается
  из живого git-состояния, которое дрейфует между Stop'ами, а дедуп идёт по session_id →
  `fact-trace` получил бы осиротевшее событие про контент, которого нет ни в одном сторе.
  → `already_saved` отдаёт хеш инкумбента.
- **№13.** `reason="session_already_saved"` был безусловен, а веток дедупа две
  (session_id / сегодняшняя дата при пустом session_id — известный класс: гонка UPS-хуков
  портит `session-skills.json`). → reason называет сработавший ключ.
- **№4.** Три отчётные поверхности (stdout, trace `applied`, баннер каденса) читали
  глобальный `args.apply` → писали «dry-run», пока reflect мутировал production.
  Зеркало чинимого бага. → `_applied_jobs()`.
- **№5.** `MEMORY_MAINTENANCE_APPLY_<JOB>` покрывает только `SUBPROCESS_JOBS`;
  для 5 инлайн-джобов — молчаливый no-op. Имя обещало обобщение, код не давал.
  → fail-closed `if name not in SUBPROCESS_JOBS` + честный docstring.
- **№6, №7, №2.** Тесты — см. 04.
- **№9.** Прибор переизобретал предикат (терял ветку `theta`) → зовёт реальный
  `reflect(dry_run=True)`.

Отложено (зафиксировано в §18 роадмапа): №8 `read_episodes` не фильтрует `archived_at`
(при `min_cluster=2` латентный конфликт с forget-gate ожил); №10 два резолва БД;
№11 `_progress` мёртв при закрытом окне; №12 fallback не снимает полуинициализированный
модуль при провале exec.

**Не подтвердилось при ревью:** контракт `on_present` для `harvest` цел (аргументы
keyword-only, дефолт `None`); спама рёбер нет (`create_link` бросает до INSERT, глотается
двумя уровнями); `format_summary` вне fail-soft практически недостижим и ловится
`protocol.py:185`.
