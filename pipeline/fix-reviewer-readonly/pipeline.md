# Пайплайн (medium): Read-only ревьюер + process-guard

Реализация 4 рекомендаций из анализа инцидента 2026-06-30 (субагент-ревьюер code-verify убил keep-alive демон через `Stop-Process`).

## 1. План
Предотвратить деструктивные действия субагента-ревьюера. 2 слоя: контракт в промпте (превентивно) + PreToolUse-гейт (defense-in-depth).

## 2. Дизайн
- **Корень:** side-effect-capable агент (`general-purpose`/`Explore` имеют shell) + рантайм-формулировка задачи + ловушка shim-doubling.
- **П.1–3:** read-only контракт ревьюера в `code-verify/SKILL.md` (Уровень 2 + 4 шаблона): только Read/Grep/Glob; запрет запуска/kill/Write; рантайм — за оркестратором; anti-trap про `.venv`=2 процесса.
- **П.4:** caller-agnostic PreToolUse-гейт (детект «субагента» ненадёжен — `agent_id` в stdin недоступен), защита по ЦЕЛИ: pid демона из lock + name-токен + broad python-kill. Matcher **`Bash|PowerShell`** (критично: `Stop-Process` — PowerShell-командлет, не покрытый Bash-матчерами).

## 3. Реализация
- [`code-verify/SKILL.md`](../../.claude/skills/code-verify/SKILL.md): контракт-блок в Уровне 2 + read-only строка в `# Роль` канона + напоминание в разделе «4 режима».
- [`process-guard.py`](../../.claude/hooks/process-guard.py): PreToolUse `Bash|PowerShell`; `_VERB_RE`/`_BROAD_RE`; `_protected_pids()` (lock `.claude/cache/*.lock`); `_PROTECTED_NAME_TOKENS`; opt-out `PROCESS_GUARD_DISABLE=1`; graceful→allow.
- `settings.json`: блок PreToolUse `Bash|PowerShell` → process-guard.py (timeout 3).

## 4. Тест (верификация)
- `py_compile` OK; JSON валиден; гейт зарегистрирован (matcher `Bash|PowerShell`).
- **8/8 pipe-тестов PASS**: BLOCK (kill protected pid / name-токен / broad python-kill / taskkill broad) + ALLOW (чужой pid / не-kill / чужой инструмент Read / opt-out).
- **Баг пойман верификацией:** `_CACHE` смотрел в `.claude/hooks/cache` вместо `.claude/cache` → pid-защита не работала → FAIL 1/8 → исправлено `.parent.parent` → 8/8.
- code-verify: ручной read-only разбор (без субагента — во избежание повтора инцидента) = PASS.
- Живое подтверждение работы гейта: он заблокировал собственную Bash-команду теста, содержавшую `Stop-Process`+`tei_keepalive` (потому тест-харнесс вынесен в файл с конкатенацией токенов).

См. память [[feedback-subagent-reviewer-readonly]], [[reference-tei-keepalive-ups-timeout]].
