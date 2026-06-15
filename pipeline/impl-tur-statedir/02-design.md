# 02 — Дизайн

## resolve_task_dir(task_dir, slug) — приоритет
1. `--task-dir D` (явный override, backward compat) → `Path(D)`.
2. `--slug S` → `pipeline_state.state_dir(S)` (папка задачи из реестра для 1С; generic → pipeline/<slug>).
3. авто: `resolve_current()` + `is_registered(cur)` (только зарегистрированная 1С) → `state_dir(cur)`.
4. иначе → None (stdout) — без сюрприз-записи для generic CURRENT.

## Загрузка pipeline_state — collision-immune
`_load_pipeline_state()` через `importlib.spec_from_file_location("_ps_for_tur", …)` — обходит коллизию
src/shared↔hooks/shared (pipeline_state stdlib-only, без side-effects). best-effort → None при сбое.

## Публичный предикат (reviewer-rec)
`pipeline_state.is_registered(slug)` — вместо опоры на приватный `_read_registry`.

## Backward compat: `--task-dir`/`--rollup`/stdout не изменены. Оркестратор run-1c-task шаг 9 → `--slug`.

## Approved: пользователь («сделай, цель — все файлы задачи в папке задачи»).
