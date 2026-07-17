# 04 — Тестирование

## Результат

- **2373 unit passed**, 2 skipped (гейт `-m unit`). Ruff по всем изменённым файлам чист
  (4 оставшихся в репо — предсуществующие, в `gate_policy.py` / `sonar_mcp_launch.py`).
- **Acceptance: ALL_PASS** (7/7), баннер `MEM-AI-ACCEPTANCE` замолчал — проверено
  запуском SessionStart-хука.

## Саботаж-проверка (11/11 RED)

Зелёный тест ничего не значит, пока не доказано, что он краснеет
([[feedback-sabotage-check-tests]]). Харнесс откатывает каждую правку и требует падения
именно её теста, затем восстанавливает файл:

| Саботаж | Тест | Итог |
|---|---|---|
| `min_cluster` назад на 3 | `test_default_min_cluster_fires_on_a_two_row_cluster` | RED |
| Захардкодить дефолт в CLI | `test_cli_defaults_come_from_the_module` | RED |
| Убрать эмит `dup` | `test_dedup_path_emits_dup_event` | RED |
| Игнорировать per-job env | `TestJobApply::test_per_job_env_opts_one_job_in` | RED |
| Отвязать `on_present` в reflection | `test_links_recorded_when_the_pattern_already_exists` | RED |
| Убрать вызов `on_present` в харвестере | `test_links_recorded_when_the_pattern_already_exists` | RED |
| Отвязать `_job_apply` от `_run_subprocess` | `test_run_subprocess_passes_apply_flag_from_per_job_env` | RED |
| Эмитить свежий хеш вместо инкумбента | `test_dup_event_carries_the_incumbent_hash_not_a_fresh_one` | RED |
| Захардкодить `reason` | `test_reason_names_the_key_that_actually_matched` | RED |
| Убрать критерий записи | `test_reflection_wrote_catches_the_return_to_dry_run` | RED |
| Врать «dry-run» при записи | `test_applied_jobs_reports_per_job_writers` | RED |

Харнесс поймал сам себя: после переписывания dup-блока якорь одного кейса устарел →
`[SKIP-BROKEN] anchor not found -> harness is lying`. Молчаливо-зелёный саботаж хуже
отсутствующего, поэтому проверка якоря встроена.

## Найдено ревью, исправлено

- `test_fresh_session_still_saves_and_reports_saved` был **вакуумно-истинен**:
  `save_to_sqlite` застаблен → реальный `_record_ingest("saved")` не срабатывал →
  `assert "dup" not in []` проходил тривиально, даже если выпотрошить `execute()`.
  → теперь пишет в tmp-БД и проверяет и строку, и событие.
- Строка проводки `apply = _job_apply(name, apply)` не была покрыта: все 4 теста дёргали
  хелпер напрямую → её удаление оставляло сюиту зелёной, а каденс молча возвращался в
  5-недельный dry-run. → 2 теста на `_run_subprocess` со стабом `subprocess.run`.
- `memory_ai_acceptance.py` не имел **ни одного** теста. Это важно: `acceptance_watch`
  глотает любое исключение из `collect_metrics`/`evaluate` → переименованный ключ
  деградирует в тишину. → [`test_memory_ai_acceptance.py`](../../tests/unit/test_memory_ai_acceptance.py):
  `test_each_criterion_can_fail` (параметризован по всем 7 — ни один не может быть
  структурно нефальсифицируемым, ровно как `archive_ran` и `reflection>=1`).

## Живая верификация

| Что | Доказательство |
|---|---|
| Триггер рефлексии ожил | `clusters_triggered` 0 → **2**; `min_cluster=2` подхвачен CLI (single-source работает) |
| `on_present` срабатывает | Зонд: **4** попытки линковки, все 4 → `Link already exists` (рёбра от 06-11, pid совпали) |
| Дедуп оставляет след | Пре-флайт Stop-хука: `{store: memory_ai, action: dup, content_hash: cbaba5ba…, reason: session_already_saved}` |
| Дедуп остался дедупом | Строк в БД **155 → 155**, `session_summary` за 17.07 = 1 (дубль не создан) |
| reflect атрибутируем | 2 события `harvester=reflection, store=learned_patterns` |
| Регресс `on_present` | Существующие тесты `pattern_harvest` зелёные — путь `harvest` не задет |

**Регресс, пойманный полным прогоном:** `test_memory_ai_chains.py::test_a3_session_save_hash_dedup_importance`
пинил `already_saved(...) is True` — легитимный слом контракта (bool → dict\|None).
Поведение сохранено (дедуп, второй строки нет); тест обновлён и **усилен**: теперь
проверяет, что хеш инкумбента совпадает с реально хранимой строкой (смысл находки №3)
и что промах даёт `None`.

## Что осталось непроверенным

- `reflection_wrote` не ловит регресс, если старые события остались в логе, а reflect
  замолчал сегодня (лог ротируется на 2МБ). Freshness-вариант («писал за последние N
  каденсов») — не сделан; для одноразового acceptance-гейта приемлемо, для живого
  мониторинга нет. Правильное место такого детектора — отчётность каденса (починена, №4).
- Открытые долги ревью (№8/№10/№11/№12) — в §18 роадмапа, не блокеры.
