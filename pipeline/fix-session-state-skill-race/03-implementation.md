# 03 — Реализация

## `shared/session_state.py` → v2.1

- `_save_state`: `os.replace` в retry-цикле — `_REPLACE_RETRIES=6` × `_REPLACE_RETRY_SLEEP=20мс` на `PermissionError` (Windows-читатель без `FILE_SHARE_DELETE`); исчерпание — прежний `raise`.
- `_ipc_lock()`: атомарный `os.open(lock, O_CREAT|O_EXCL)`; ожидание ≤0.6с (poll 20мс), stale >5с — взлом (`unlink`+retry), недоступность — fail-open (мутация без лока лучше дедлока хука с timeout 3с). Cleanup fd+unlink в finally.
- `_read_disk_fresh()`: чтение строго с диска (мимо `_state_cache`) — кэш к моменту мутации может быть протухшим.
- `_mutate(fn)`: `_lock` (потоки) + `_ipc_lock` (процессы) → fresh read → `fn(state)` → save (`fn`→`False` = no-op, кэш обновляется снапшотом). **Все 13 мутаторов** переведены; `reset_session` — под `_ipc_lock`. Читатели не тронуты.
- Реентерабельность: `_read_disk_fresh`/`_save_state` не берут `_lock` (не реентерабелен) — `_mutate` держит его снаружи; `_load_state` из-под `_mutate` не зовётся.

## `code-skill-enforcer.py` → transcript-fallback

- `_skill_activated(inp, skill)`: state → иначе `_skill_in_transcript` (хвост ≤2МБ, префильтр `'"Skill"' + имя` до JSON-парса, поиск `tool_use{name:Skill, input.skill==<требуемый>}`) → self-heal `add_activated_skill`. Вызов фолбэка ТОЛЬКО на would-block пути (state пуст) — на обычные Write/Edit накладных нет.
- Три call-site (Levels A/B/C) переведены на `_skill_activated`. Level A.1 (`learn:`-маркеры) — на state, как было.

## Попутное

- CLAUDE.md: заметка в блоке Enforcement-надёжности (v2.1 + ссылка на пайплайн).
- Дорожная ирония: правку энфорсера заблокировал сам энфорсер (Level A паттерн `Skill\s*\(` в новом коде → `doc-to-skill`) — штатно, закрыто активацией скилла; НЕ ложный блок класса инцидента (запись активации при этом отработала — фикс уже жил на диске).
- `shared/hook_lock.py` сознательно НЕ использован: его `acquire_lock` — read-check-write JSON без атомарности (TOCTOU, оба «берут» лок) — для мьютекса мутаций непригоден. Не трогал (отдельный долг).
