# Аудит 260710 - реализованные пункты roadmap 260708 (Autonomous 1C Debugging)

> **Дата:** 2026-07-10
> **Метод:** 4 параллельных адверсариальных ревью-агента (read-only, по кластерам W1 ядро / W3 A2+A3 / B3+B4 async / B2+C0+B5) + live-прогон тестов + собственные операционные проверки. Все находки - с file:line по фактическому коду `tools/bsl-debug-server` @ `d7a173b`.
> **Скоуп:** реализованное - W1 (W1.0/A0/A1/C0/B2), W2 (B3/B5.a-d), W3 (A2/A3/B4). НЕ скоуп: нереализованные B1/C1/W4/W5.
> **Верифицированные заявления роадмапа:** «425 unit passed» - подтверждено живым прогоном (425 passed, 37.5s) ✅; `autonomy.py` в HMR watch-list ✅; lost-wakeup-инвариант B3 - формально подтверждён интерливинг-анализом ✅.

## Вердикт

Инженерное качество высокое (честные тесты, системная отработка Ф-2 в ядре, Continue-в-finally, атомарные персисты, backward-compat дисциплина B5), но **аудит нашёл 1 CRITICAL (security) + 6 HIGH (корректность)**, из них два - прямое опровержение заявлений роадмапа («self-cancel класс закрыт» B4; «offset-кэш dict[(object_id, property_id)]» B2). Общий паттерн дефектов: **per-diff code-verify пропускает межфичевые взаимодействия** (A3-logpoint'ы × `_await_bp_stop`-debounce; HMR-restart × two-phase state; UI+ эскалация × heartbeat) и **точечный фикс вместо закрытия класса** (self-cancel починен в одном из двух путей).

---

## 1. CRITICAL

### C-1. Креды всё ещё извлекаются из истории ПУБЛИЧНОГО форка (B5.d закрыт наполовину)
`git show c65d965:start-1c-debug.bat` на origin `github.com/Alex1980Alex/bsl-debug-server` (public) отдаёт:
```
... /N"a.terletskiy@sodru.com" /P"Alex80Alex" /Debug ...
```
B5.d удалил файл только из HEAD (c8abae8); коммит достижим в истории. Working tree чист (Grep подтвердил).
**Действия:** (1) ротация пароля `Alex80Alex` - уже помечена PENDING за пользователем, теперь БЛОКЕР; (2) history-rewrite (git filter-repo/BFG) + force-push + запрос GitHub Support на GC dangling-объектов - либо осознанно принять «rotation-only» и зафиксировать это решением (сейчас статус двусмысленный: роадмап пишет «история не переписывается (прецедент rotation-only)», но ротация не выполнена → фактически креды живые и публичные).

## 2. HIGH (корректность)

### H-1. Self-cancel класс НЕ закрыт: UI+ эскалация из ping() убивает heartbeat и auto-reattach навсегда (B4)
`mcp_debug_server.py:472-485 + :1369`. B4 починил `detach(cancel_ping=False)` только в `_attempt_reconnect`. Но `ping()` (исполняется в `_ping_task`) при 400 «UI+ не зарегистрирована» уходит в `_ui_plus_full_reattach_and_retry` → `:476 await self.detach()` с дефолтным `cancel_ping=True` → `self._ping_task.cancel()` на самом себе → CancelledError (BaseException, не ловится `except Exception`) → `_ping_loop` тихо умирает вместе со всем B4-механизмом. `pingDebugUIParams` отсутствует в exclusion-списке `_post` (:409-415); комментарий «All other callers run outside the loop» (:1228) фактически неверен.
**Фикс:** исключить `pingDebugUIParams` из `_ui_plus_retry` ИЛИ в эскалации `cancel_ping = asyncio.current_task() is not self._ping_task`. Регрессия: тест «эскалация из ping-таска → луп жив».
**Мета-урок:** адверсариальный verify поймал этот же класс в `_attempt_reconnect` - но фикс был точечный; нужен был Grep всех путей к `detach()` достижимых из `_ping_task`.

### H-2. «Ghost» stopped-target после force-resume ломает все последующие collect'ы (W1/A1)
`mcp_debug_server.py:1700-1705 + 3846-3851`. `step()` снимает таргет из `_stopped_targets` только ПОСЛЕ успешного `_post`. Платформа force-resume'ит JOB (штатное закрытие halt-окна 1-2с, RDBG resume-событий не шлёт) → finally-Continue автотрейса получает 400 и глотает (`except: log.warning`) → discard не выполняется никогда. Каждый следующий `debug_autotrace(collect)` мгновенно «хитит» призрак через state-predicate `_await_bp_stop` и строит bundle из устаревшего `_last_stack_by_target` → INCONCLUSIVE/мусорный вердикт.
**Фикс:** `discard` в `finally` внутри `step()`; в `_await_bp_stop` - liveness-проба кандидата (дешёвый getCallStack).

### H-3. Ф-2 пропущен в exception_bps: `exception_module`-фильтр матчится по OUTERMOST-фрейму (A2)
`exception_bps.py:48-55`: `top = stack[0]`. При Ф-2-фиксе `bp_conditions.py:32` и `coverage.py:42` переведены на `reversed(stack)`, exception_bps - нет. `debug_root_cause(exception_module="МойМодуль")` сверяет паттерн с entry-point JOB, а не с бросившим модулем → фильтр не матчится → `maybe_suppress` авто-Continue'ит именно то исключение, которое ловили → NO_HIT. Тот же класс бага, который уже чинили для `message_pattern` (root-fix `info` в этом же файле, :37-40).
**Фикс:** матчить по `reversed(stack)` (или по всем фреймам).

### H-4. HMR-restart между arm и collect: orphan-logpoint'ы превращаются в неснимаемые user-visible halt'ы (A3, затрагивает A2)
`mcp_debug_server.py:356, 4071, 1896-1902`. `.active.json` персистит только `session_id` + `line_offsets`; `_trace_var`/`_logpoints`/`_set_breakpoints_cache`/`_exception_bp_filters` - in-memory. Для HMR-сервера restart - штатный режим: arm → edit → restart → `_logpoints` пуст → `fire_logpoint` возвращает False → стоп НЕ подавляется: каждая протрейсенная строка теперь жёстко останавливает rphost без auto-Continue, и снять их нечем (`_reapply_bp_workspace` при пустом кэше - noop :1731).
**Фикс:** персистить logpoint/trace-state в `.active.json`, ЛИБО при restore с пустым кэшем пушить ПУСТОЙ workspace (лучше потерять BP, чем получить неснимаемые halt'ы).

### H-5. A2 collect vs targetQuit: уже увиденное исключение теряется → ложный `hit:false`
`mcp_debug_server.py:3927 + 1036-1041`. Диагноз строится ЛЕНИВО в collect, а два MCP round-trip'а (arm → триггер через другой MCP-сервер → collect) легко превышают halt-окно 1-2с. `targetQuit` снимает таргет и делает `_last_exception_by_target.pop()` → collect возвращает `{hit:false}`, хотя `rteProcessing` держал в руках стек и exception (snapshot.record уже сохранил стек - но diagnosis из него не строится).
**Фикс:** eager-сборка symptom+propagation_path прямо в `_handle_command(rteProcessing)` (кольцевой буфер «последних диагнозов»); collect отдаёт degraded record с флагом `window_closed` вместо ложного miss.

### H-6. B2 offset-ключ - только `object_id`, заявленная схема `(object_id, property_id)` НЕ реализована
`mcp_debug_server.py:104-106, 4751`. ObjectModule/ManagerModule/RecordSetModule делят один корневой object_id (различие - только property_id, `uuid_index.py:32-39`). Калибровка ManagerModule (+3) молча сдвигает следующий BP в ObjectModule того же документа. Комментарий у персиста «per-module line offsets» (:3164) противоречит фактическому per-object ключу.
**Фикс:** ключ `(oid, pid)`, сериализация `"oid:pid"` в JSON.

### H-7. B2 stale offset: измеренный offset==0 не сбрасывает старый; инвалидации нет вообще
`mcp_debug_server.py:4748`: `if entry["offset"]:` - falsy-проверка. После редеплоя, выровнявшего строки, повторная калибровка (offset=0) НЕ стирает старый +3 → все BP продолжают сдвигаться. Инвалидации после `update_database`/деплоя/правки src нет; `.active.json` без TTL. Stale offset хуже отсутствия offset - ровно тот случай.
**Фикс:** `is not None` + `pop(oid)` при 0; сохранять fingerprint `.bsl` модуля на момент калибровки и сбрасывать при расхождении; минимум - чистить `_line_offsets` в `debug_connect` и документировать.

## 3. MEDIUM

| # | Дефект | Где | Суть |
|---|---|---|---|
| M-1 | **Debounce 0.15s проигрывает deferred-drain** (кросс-подтверждено ДВУМЯ независимыми агентами) | `_await_bp_stop:2026-2029` vs `logpoints.py:154-171`, `_handle_command:896/906` | Таргет попадает в `_stopped_targets` ДО решения о подавлении; deferred eval logpoint'а (сетевой round-trip, легко >150мс) держит его там → collect принимает ПОДАВЛЕННЫЙ стоп за свой hit: bundle с чужого фрейма + двойной Continue. Особенно реально при одновременно armed `debug_trace_variable`. Фикс: state-фильтр (`_user_visible_stops` set, наполняемый ПОСЛЕ suppress-гейтов - сигнал `_signal_bp_stop` уже стоит в правильном месте), debounce оставить страховкой |
| M-2 | Autotrace: нет корреляции hit↔armed BP + BP не снимается | `:3809, 3764-3851` | Collect принимает ЛЮБОЙ reason="breakpoint" стоп (чужой/pre-arm/от прошлого autotrace) и finally-Continue релизит перехваченный ЧУЖОЙ halt. BP после collect/NO_HIT не убирается (у A3 есть `_clear_logpoint_keys`, у A1 аналога нет) → следующий проход кода халтит rphost, когда никто не собирает |
| M-3 | Verdict: eval-timeout → ложный FAIL, не INCONCLUSIVE | `eval_expression:1668-1675` → `_extract_eval_value` → `autonomy.py:153-169` | Таймаут возвращает `[]` → actual=`"[]"` → `ok=False` без `any_error` → FAIL («агент доказал баг, которого нет»). Смежно: `valueBoolean` перекрывает `pres` (`autonomy.py:110-125`) → expect «Истина» vs actual «true» = ложный FAIL на булевых. Фикс: `[]`/`error`-state → INCONCLUSIVE; `pres` проверять ДО typed-ключей |
| M-4 | A3 collect не ждёт in-flight deferred-задачи → хвост таймлайна теряется | `:4102-4111`, `logpoints.py:16-17` | Последний hit ещё в eval'е → его нет в JSONL на момент чтения; запись допишется после collect и осиротеет (или попадёт в СЛЕДУЮЩИЙ трейс - ключи совпадают). Фикс: `await asyncio.wait(_active_tasks, timeout=2)` перед чтением |
| M-5 | A3 молча уничтожает ЧУЖИЕ BP/logpoint'ы на тех же строках | `_record_logpoint:1774-1778`, `_clear_logpoint_keys:2043-2062` | Arm перезаписывает пользовательский logpoint без предупреждения; collect вырезает строки из ЛЮБОЙ cache-entry (включая обычный BP пользователя). Фикс: пометка владельца ключа + отказ/предупреждение при коллизии |
| M-6 | B4 reconnect: частичный провал + разрушение активного стопа | `_attempt_reconnect:796-823`, `_maybe_reconnect:757-768` | (a) handshake упал после attach → `_recovery` лжёт «провал» при полуживой сессии, старая сессия висит на dbgs; провал BP-reapply → `return True`, BP тихо потеряны. (b) 3 медленных ping'а (httpx timeout 30с) при ЖИВОМ dbgs → деструктивный reconnect с новым session_id, пока пользователь смотрит variables. Фикс: guard `if self._stopped_targets: return False`; отдельный короткий таймаут ping-POST (~5с); `_recovery["handshake_ok"]`/`["bp_reapply_failed"]`; backoff 30→60→120→300с |
| M-7 | `coverage_register` НЕ применяет B2-offset | `:4560-4575` | Асимметрия: BP/logpoint/autotrace сдвигают, coverage - нет → на дрейфнутом модуле BP попадёт, coverage мимо. Фикс: применить или явно задокументировать |
| M-8 | Двойная коррекция offset | `debug_calibrate_result` → `debug_set_breakpoint:4254` | `nearest_fired` возвращается в deployed-координатах; BP на неё получает ЕЩЁ +offset. Нет opt-out (`apply_offset: bool`) |
| M-9 | Тесты пишут в живой `.active.json` | `tests/test_calibration.py:121-151` | `_ACTIVE_SESSION_PATH` монкипатчится только в test_mcp_debug_server.py → локальный pytest затирает HMR-persistence bogus-сессией. Фикс: autouse-fixture в conftest.py → tmp_path |
| M-10 | C0: Соответствие/РезультатЗапроса деградируют тихо/мусорно | `autonomy.py:74-81, 95-132`, `:4132` | `X[i]` для Соответствия → молча `Неопределено`-страницы; `.Количество()` у РезультатаЗапроса не существует → в `count` уезжает str() мусор. Docstring сам рекомендует РезультатЗапроса. Фикс: гейтить `_page` по `type` из `collection_info` + hint «выгрузи через .Выгрузить()» |
| M-11 | A2 строит diagnosis в halt-окне с unbounded latency-хвостом | `build_diagnosis_record` × `eval_locals_auto:1540` | 3 фрейма × batch-eval; при закрытии окна посреди обхода каждый следующий фрейм ждёт async-таймаут до 10с (суммарно до ~30с). Graceful (partial record), но latency не bounded и не сюрфейсится |

## 4. LOW (сводно)

- `_extract_upstream` (autonomy.py:427-450): строковые литералы не вырезаются из RHS → идентификаторы внутри строк становятся «upstream» (мусорные eval-error в таймлайне); `//` внутри строки (`"http://…"`) режет RHS; `Новый ТаблицаЗначений;` без скобок → тип в upstream. Фикс: `re.sub(r'"[^"]*"', '""', rhs)` (кавычка в BSL-строке удваивается - жадный вариант безопасен) + skip идентификатора после `Новый`.
- `find_assignment_lines` FN-классы: `Для X = 1 По`, второй оператор в строке (`А=1; X=2`), перенос выражения после `=` (upstream пуст).
- A2 arm копит дубликаты фильтров в `_exception_bp_filters` (нет дедупа/снятия в collect).
- `_trace_var = None` ставится безусловно при провале cleanup'а (:4004-4005) → orphan-ключи прежнего трейса недостижимы для очистки.
- `_extract_message` только `isinstance(str)` - вложенный dict в `info` → фильтр подавит нужное исключение (hardening-gap).
- `max_frames=0` → `fault_location=None` при вычислимом fault-фрейме.
- Метрики `_stop_events.lineNo`/`_bp_by_location` по `stack[0]` (outermost) - Ф-2-sweep не тронул (:957-978) → session_summary врёт про строку BP.
- Docstring autotrace ссылается на несуществующий `raw.stack` (:3756).
- `eval_locals_auto` не отсекает отрицательный `stack_level` (:1555) - рассинхрон с guard'ом autonomy.py:207.
- Eval-выражения не XML-экранируются (`_calc("expression", ...)` :1489) - легитимный BSL с `<`/`&` ломает запрос; `_escape_xml` есть, применяется только к condition.
- B5.a: alias-lookup регистрозависимый, отсутствие в map → ТИХИЙ fallback на дефолтный src (неверные resolved_source без warning'а); `_cache_path_for` sha1 от ненормализованного пути (trailing slash/регистр диска → дубли кэшей; смена пути → сироты копятся).
- Offset-lifecycle: явный `debug_connect` создаёт новый клиент с пустыми `_line_offsets` и перезаписывает `.active.json` - HMR переживает, ручной reconnect теряет (недокументировано).
- `RecordSetModule` UUID → `("ManagerModule.bsl", None)` в `MODULE_PROPERTY_FILES` (uuid_index.py:36) - в EDT-экспорте RecordSetModule.bsl существует отдельно; резолв укажет не туда (pre-existing).
- Локальный `coverage.py` затеняет pip-пакет coverage (сломает pytest-cov при добавлении).
- Debounce re-check не перепроверяет reason (:2028).
- pytest-warning: sync-тест с `@pytest.mark.asyncio` (test_mcp_debug_server.py:1381).

## 5. Операционные наблюдения (вне кода)

1. **W3 не запушен**: сабмодуль ahead 3 (acb8ac3/03e7b84/d7a173b = A2/B4/A3) → CI публичного форка W3 не прогонял; решение о публикации wrapper-кода - открытое (осознанно, но статус в роадмапе не отражён).
2. **HMR watch-list неполный**: урок P0.D применён к `autonomy.py` ✓, но `logpoints.py`/`exception_bps.py`/`bp_conditions.py`/`system_stops.py`/`coverage.py`/`snapshot.py` в `--watch` НЕТ → их правка не перезагружает сервер (тот самый класс «фикс не работал до /mcp reconnect»).
3. Событийная петля одна: весь ping под общим httpx-таймаутом 30с - один зависший POST останавливает и adaptive-каденс (ACTIVE 0.1с), и heartbeat-детекцию (~96с до срабатывания).

## 6. Мета-выводы по процессу (для следующих волн)

1. **Класс, а не инстанс.** Два дефекта этого аудита (H-1 self-cancel, H-3 Ф-2 в exception_bps) - «уже чиненные» классы, оставшиеся в соседних путях. После каждого класса-фикса - механический Grep всех аналогичных сайтов (пути к `detach` из ping-таска; все `stack[0]` по репо).
2. **Per-diff verify ≠ межфичевой аудит.** «code-verify PASS по каждому пункту» - честно, но 5 из 7 HIGH живут на СТЫКАХ фич (A3-logpoints × debounce; HMR × two-phase state; эскалация × heartbeat; targetQuit × lazy collect). В конце волны нужен wave-level интеграционный проход с матрицей взаимодействий.
3. **Two-phase - источник целого класса гонок** (HMR между фазами, targetQuit, чужие стопы, потерянный хвост JSONL). Отложенный transport (a) HTTP one-call (Ф-1) схлопывает окно arm→collect - поднять его приоритет; там, где two-phase остаётся, - персистить фазовое состояние.
4. **B1 подтверждён как корень**: halt-окно 1-2с - первопричина H-2/H-5/M-11. Приоритет B1 (persistent JOB, ADR-049) правильный.
5. **Тестовая дисциплина хорошая, но слепые зоны системны**: нет ни одного HMR-restart-сценария, ни одного «двое конкурентных collect'ов», ни failed-Continue. Добавить в шаблон тестов волны обязательные негативные сценарии: restart между фазами, конкурентные waiter'ы, транспортный сбой в finally.

## 7. Предлагаемая волна W-fix (приоритизировано, ~10-14ч)

| # | Фикс | Покрывает | Усилие |
|---|---|---|---|
| 1 | Ротация пароля + решение history-rewrite vs rotation-only | C-1 | 0.5ч + внешнее |
| 2 | `pingDebugUIParams` из `_ui_plus_retry` / `current_task`-guard в эскалации + регрессия «луп жив» | H-1 | 1ч |
| 3 | `step()` discard в finally + liveness-проба в `_await_bp_stop` | H-2 | 1ч |
| 4 | `reversed(stack)` в `exception_bps._extract_top_module_name` + Grep остальных `stack[0]` (метрики :957) | H-3, LOW-метрики | 1ч |
| 5 | Персист logpoint/trace-state в `.active.json` ИЛИ пуш пустого workspace при restore | H-4 | 1.5ч |
| 6 | Eager diagnosis-буфер в `rteProcessing` + degraded record `window_closed` | H-5 | 2ч |
| 7 | B2: ключ `(oid,pid)` + `is not None` + инвалидация на connect + `apply_offset` opt-out + offset в coverage_register | H-6, H-7, M-7, M-8 | 2ч |
| 8 | `_user_visible_stops` state-фильтр вместо debounce | M-1 | 1.5ч |
| 9 | Autotrace: hit↔armed корреляция + снятие BP в collect/NO_HIT | M-2 | 1.5ч |
| 10 | Verdict: `[]`/error → INCONCLUSIVE; `pres` перед typed | M-3 | 1ч |
| 11 | A3: await deferred tasks + владелец logpoint-ключа | M-4, M-5 | 1.5ч |
| 12 | B4: guard активного стопа + короткий ping-таймаут + backoff + `_recovery` поля | M-6 | 1.5ч |
| 13 | conftest autouse-fixture `.active.json` → tmp_path | M-9 | 0.5ч |
| 14 | Дополнить `--watch` в `.mcp.json` всеми модулями | Опер.2 | 0.2ч |

## 8. Что сделано хорошо (баланс)

- **W1.0 хелперы честно внедрены** - все заявленные сайты переведены (`_resolve_property_id` ×6, `_resolve_stopped_target` ×7), дублей не осталось.
- **Ф-2 в ядре системен и live-датирован**: `build_frame_bundle`, `eval_locals_auto`, `build_diagnosis_record`, bp_conditions/coverage - с тестами, не мокающими индексацию (exception_bps - единственный пропуск).
- **Lost-wakeup инвариант B3 реально соблюдён** (state до set, clear→re-check без await, 1с cap) - подтверждён интерливинг-анализом, не только декларацией.
- **Continue-в-finally присутствует в обоих two-phase инструментах**; graceful-деградации A0 продуманы и покрыты.
- **Честное усечение** (`frames_bounded`/`frames_total`, `lines_bounded`) - cap виден вызывающему.
- **Тесты в большинстве честные**: реальный loop/Event в B3/B4, `_wire_reconnect` принципиально не мокает `detach`, `test_does_not_cancel_live_ping_task` реально ловит старый баг; pure-хелперы A3 гоняются на живом BSL с кириллицей и негативными ассертами.
- **B5 backward-compat дисциплина**: unset env → бит-в-бит прежнее поведение; malformed env покрыт; per-src кэш против clobbering; `partition("=")` для Windows-путей.
- **CI честный**: compileall всех 12 модулей, ~416 платформо-независимых тестов реально пройдут на ubuntu.
- **B5.b fingerprint только `*.mdo` - корректен для СВОЕГО кэша** (UUID→path не зависит от контента .bsl; ловушка аудита не подтвердилась) - реальный stale-канал после правки .bsl не uuid-кэш, а B2-offset (H-7).
