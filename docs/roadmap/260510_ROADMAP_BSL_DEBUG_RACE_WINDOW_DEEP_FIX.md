# Roadmap — Глубокий фикс post-BP-fire UI+ registration race window

**Дата:** 2026-05-10
**Статус:** 🟡 PROPOSED — production-blocking finding для eval/step pipeline (BP-fire scope закрыт `debug_break_on_next` 2026-05-10, см. [260508 §10](260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md#L)). Этот roadmap концентрируется ТОЛЬКО на UI+ registration bug на пути eval/variables/step после BP fire. До 2026-05-10 trigger через 1c-mcp-crud вообще не доходил до BP fire (separate, более ранний баг).
**Приоритет:** Высокий (закрывает P1 acceptance из 260508)
**Связано:** [`260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md`](260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md), [cache `dbgs-rdbg-debug-server.md`](../../.claude/skills/1c-doc-research/cache/dbgs-rdbg-debug-server.md)

---

## 0. Контекст: что показала real-world валидация (2026-05-09)

При попытке real BP-fire validation против running 1С (`ИБTransportManagementDevelop`, `Документ.гкс_ЛабораторныйАнализ.ОбработкаПроведения:141`) был обнаружен **production-blocking баг**, который **roadmap 260508 P1.2 не закрыл**, а только обошёл на optimistic happy path.

### Sequence наблюдений

1. ✅ User провёл документ → 1cv8c.exe «завис» (BP fire confirmed visually)
2. ✅ `debug_targets` → target в `state: StopOnNextLine`, `stopped_target` UUID resolved
3. ❌ `debug_stack_trace` → generic error / 204 No Content
4. ❌ `debug_variables` → HTTP 400 «UI+ - часть отладки не зарегистрирована»
5. ❌ `debug_evaluate("ТекущаяДата()")` → HTTP 400 «UI+ - часть отладки не зарегистрирована»
6. ❌ `debug_step("Continue")` → HTTP 400 «Предмет отладки не зарегистрирован»

### Что не сработало в P1.2 fix

`RDBGClient._ensure_target_attached` принимает `target_uuid`, проверяет `_known_attached_targets` cache, и если target там уже есть — skip'ает re-attach. После initial connect cache populated, поэтому idempotent guard НЕ делает re-attach.

Force re-attach (`attach_debug_targets([TARGET])`) тоже не помогает: RDBG возвращает HTTP 200 OK на attachDetachDbgTargets, но subsequent evalLocalVariables всё равно даёт «UI+ - часть отладки не зарегистрирована».

**Это значит, что между BP fire и нашим eval call теряется не просто attach state, а более глубокая «UI+ часть» регистрации, которую `attachDetachDbgTargets` сам по себе не восстанавливает.**

### Side effect — P2.1 entry-line empty-array

`debug_variables` возвращал `variables: []` ранее в 260508 P2.1. Тогда подозревали schema issue / stack_level. Теперь ясно: это **same registration loss bug** — RDBG возвращает empty array вместо 400 в некоторых ситуациях.

---

## 1. Гипотезы (требуют wire capture для подтверждения)

### Гипотеза A — нужна обязательная ping-consumption stop event'а

yukon39 ContextServerEventSubscriber dispatch'ит push events (`DBGUIExtCmdInfoCallStackFormed`) при ping. **Возможно, RDBG требует чтобы UI consumed stop event через ping перед evalLocalVariables**, иначе считает target в pre-stop state (registration not «activated» for stopped state).

**Implication:** наш `_ping_loop` крутится в фоне и должен консумить event'ы. Но у нас он работал в long-running MCP server. В прямом скрипте без ping_loop event может не быть consumed.

**Тест:** в обоих случаях — live MCP с active ping_loop И прямой скрипт без — eval failed одинаково. Это **не подтверждает** гипотезу A.

### Гипотеза B — fresh attachDebugUI session не наследует BP fire context

Когда live MCP делает attach под session A, BP set'ятся под session A. Target stops. Если потом fresh wrapper instance attach'ится под session B и пытается eval — RDBG говорит «UI+ - не зарегистрирована» потому что stop state привязан к session A, но запрос идёт от session B.

**Тест:** даже в **live MCP** (одна и та же session с момента set BP до eval) eval failed. **Не подтверждает** гипотезу B.

### Гипотеза C — между BP fire и eval target auto-resumed

1С может иметь internal timeout: если debug UI не реагирует на stop-event в течение ~10s, target auto-continues. К моменту eval target уже Worked, и «не зарегистрирована» — это «target не stopped».

**Тест:** `debug_targets` показал `state: StopOnNextLine` НА МОМЕНТ eval call. Если target resumed, это бы показало `Worked`. **Не подтверждает** гипотезу C.

### Гипотеза D — нужен дополнительный handshake step (HIGH PROBABILITY)

Возможно, EDT Debugger UI после BP fire делает какие-то additional RDBG calls, которые «активируют» UI+ registration для stopped state. Например:
- `setBreakOnNextStatement` для активации step-mode
- `getDbgTargetState` для re-confirm registration
- Пингает несколько раз с consume всех pending events до eval

**Метод проверки:** wire capture (mitm-proxy / wireshark) от EDT с активной debug-сессией. Запустить EDT, set BP в том же модуле, провести документ, capture XML traffic между EDT и :1550. Compare с нашей последовательностью.

---

## 2. Phase 1 — Wire capture EDT vs наш wrapper

**Effort:** 2-3ч
**Outcome:** точная diff между EDT post-fire sequence и нашей.

### 2.1 Setup wire capture environment

- mitmproxy as transparent proxy между EDT и dbgs.exe
- Альтернатива: wireshark + dissection HTTP XML

### 2.2 EDT scenario capture

1. Запустить EDT, attach к `ИБTransportManagementDevelop`
2. Set BP на ту же `Документ.гкс_ЛабораторныйАнализ:141`
3. User проводит документ
4. EDT останавливается на BP, показывает variables/stack
5. Capture полный XML wire trace

### 2.3 Сравнить с нашим wrapper trace

Из step 2.2 захвачен EDT post-fire sequence. Из логов нашего wrapper извлечь:
- Все RDBG calls между BP fire и failed eval
- Diff с EDT — что EDT делает дополнительно

**Output:** Список missing RDBG calls в нашей последовательности.

---

## 3. Phase 2 — Implement correct post-fire sequence

**Effort:** 1-2ч после Phase 1
**Зависит от Phase 1 outcome.**

### Возможные изменения (заранее не известны до Phase 1):

- Добавить вызов `<missing-RDBG-call>` в `_handle_command` для `callStackFormed` event
- Изменить `_ensure_target_attached` — не доверять local cache, делать probe (`getDbgTargetState`) и re-issue полную registration sequence если probe fails
- Добавить explicit ping consume перед eval/step (mitre RDBG await pattern)

### Acceptance criteria

- [ ] `debug_variables()` после BP fire returns ≥1 var
- [ ] `debug_stack_trace()` returns ≥1 frame
- [ ] `debug_evaluate("ТекущаяДата()")` returns datetime
- [ ] `debug_step("Continue")` resumes client успешно

---

## 4. Phase 3 — Update tests + cache + docs

**Effort:** 1ч

- Добавить regression test (mock RDBG returning 400 «UI+ - не зарегистрирована» → wrapper recovers через correct sequence)
- Update cache `dbgs-rdbg-debug-server.md` §13.13 с findings (изменить на §13.18 «Post-BP-fire UI+ registration handshake — actual sequence»)
- Update 16.7 §16.7.10 с known limitation (если Phase 2 не fully resolves)

---

## 5. Risks & Open questions

### 5.1 EDT может использовать undocumented RDBG calls

Если EDT шлёт что-то типа `_internal_stopped_ack` — этот URL может не работать from external clients. Workaround: explicit re-set всё (initSettings → attachDetachDbgTargets → set BP again → wait stop state confirmed via getDbgTargetState).

### 5.2 Different behavior для Server vs ManagedClient targets

Real test'ы прошли только на `targetType: Server` (rphost). ManagedClient может иметь другую registration behavior. Phase 1 capture должен покрыть оба типа.

### 5.3 1С platform version dependency

8.3.27 vs 8.3.10 могут иметь разные RDBG protocol invariants. Проверить на нашей версии 8.3.27.1936.

---

## 6. Альтернатива — accept limitation

Если Phase 1 wire capture показывает что EDT использует undocumented internal API, который мы не сможем easily реплицировать:

- Документировать как **known limitation** в 16.7
- Wrapper полезен для: BP set, target tracking, **визуальная индикация stop state**
- Для eval/step рекомендовать использовать EDT directly

Это honest fallback — лучше задокументировать ограничение чем maintain broken workaround.

---

## 7. Decision points

1. **Когда начинать?** Phase 1 (wire capture) — после того как пользователь сможет настроить mitmproxy против EDT (нужен интерактивный setup, нельзя выполнить полностью автоматически).
2. **Альтернатива:** заглянуть в yukon39 vsc-bsl-dap (VS Code DAP plugin для BSL) — там видно что происходит post-fire в Java implementation; возможно решение там описано.

---

## 8. Ссылки

- [yukon39/bsl-debug-server](https://github.com/yukon39/bsl-debug-server) — Java RDBG implementation
- [yukon39/vsc-bsl-dap](https://github.com/yukon39/vsc-bsl-dap) — VS Code DAP плагин для BSL (рекомендуется для Phase 1 alt path)
- [`tools/bsl-debug-server/mcp_debug_server.py`](../../tools/bsl-debug-server/mcp_debug_server.py) — текущий wrapper (1099 lines, race window detected at line 459-477 `_ensure_target_attached`)
- [Roadmap 260508 §1.2](260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md) — original "re-attach в tools" plan, **insufficient**
- Real-world test session log: 2026-05-09 22:35 — proof-of-bug
