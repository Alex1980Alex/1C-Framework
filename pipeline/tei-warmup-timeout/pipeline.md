# Пайплайн (trivial/medium): UPS-таймаут memory-first-hook + TEI keep-alive

Задача из диагностики: «UserPromptSubmit hook timed out after 5s — output discarded».

## 1. План
Устранить таймаут UPS-хука на входе промпта. Две меры: (1) поднять таймаут хроническо-медленных UPS-хуков 5→10 c; (2) держать TEI-эмбеддер тёплым, чтобы убрать cold-start джиттер.

## 2. Дизайн
- Корень по логу `hook-invocations.jsonl`: `memory-first-hook` avg **3642 мс** / max **4679 мс** при лимите 5 c (TEI-эмбед + мультиколлекционный Qdrant RRF + lexical arms). `prework_dispatcher` тоже на 5 c.
- TEI `pdf-rag-tei:8080` healthy 24ч, но холодный вызов ~385 мс vs warm ~80 мс (комментарий хука: cold ~600 / warm ~80).
- Решение: (а) `settings.json` таймауты обоих хуков 5→10; (б) keep-alive демон, пингующий `POST http://localhost:8080/embed` каждые 240 c, single-instance через heartbeat-lock, bounded 6ч, спавн из SessionStart-хука детачем.

## 3. Реализация
- `.claude/settings.json`: `memory-first-hook.py` и `shared/prework_dispatcher.py` → `"timeout": 10`; зарегистрирован SessionStart-хук `tei-warmup-on-start.py` (`statusMessage: tei-warmup`).
- [`scripts/tei_keepalive.py`](../../scripts/tei_keepalive.py) — keep-alive (heartbeat-lock `.claude/cache/tei-keepalive.lock`, `--once`, opt-out `TEI_KEEPALIVE_DISABLE=1`, env interval/duration).
- [`.claude/hooks/tei-warmup-on-start.py`](../../.claude/hooks/tei-warmup-on-start.py) — SessionStart, детачит демон (паттерн `ci-catchup-on-start`).

## 4. Тест (верификация)
- JSON валиден; оба таймаута = 10 (проверено парсингом).
- `py_compile` обоих новых файлов — OK.
- `tei_keepalive.py --once` rc=0; **warm-замер 36 мс против холодных 385 мс** (~10×).
- Pipe-тест SessionStart-хука: корректный `systemMessage`, демон спавнится, lock создаётся.
- Дедуп: после 3 спавнов число процессов держится на 2 (= один логический демон: шим+реальный, [[feedback-venv-python-shim-doubles-process]]); parent-child 48828→15544 подтверждён.
- docs-change-enforcer pre-flight rc=0 (новый хук не блокирует завершение).
