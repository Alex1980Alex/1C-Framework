# Этап 0: Preflight — детали (шаги 2-6)

Продолжение шага 1 (проверка трёх ключевых серверов через `ToolSearch`) из SKILL.md.

2. **TCP-probe ключевых портов** — отдельный сигнал от наличия MCP-tool в сессии (tool может быть зарегистрирован, но HTTP-bridge упасть):

   | Порт | Сервис | Команда | Ожидание |
   |---|---|---|---|
   | `:8765` | EDT-MCP HTTP-bridge | `Test-NetConnection -ComputerName localhost -Port 8765 -InformationLevel Quiet` | `True` для режимов **Full** и **Code-only** |
   | `:1550` | 1С debug agent (`ragent.exe -debug`) | `Test-NetConnection -ComputerName localhost -Port 1550 -InformationLevel Quiet` | `True` только если нужна runtime-отладка в Этапе 4 |

   Альтернатива одной командой:
   ```powershell
   python scripts/smoke_test_implement_1c_task.py
   ```
   Скрипт парсит [.mcp.json](../../../../.mcp.json), TCP-probe + MCP-handshake, возвращает exit-code `0` (Full) / `1` (degraded) / `2` (unusable). Подробности: [16.6 EDT-MCP setup](../../../../docs/framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md).

3. **Debug environment health** — вызвать `mcp__1c-debug-hmr__debug_health_check(mode="probe")` (structured <1с health-check вместо 5-7 manual probes). Парсить ответ:

   - `ready: true` → BP-verification в Этапе 5 доступна, продолжить
   - `ready: false` + непустой `auto_prepare_available[]` → предложить пользователю prepare-actions (whitelist: kill-stale-rphosts, restart-ragent через `mode="prepare"`); НЕ запускать без подтверждения (shared-state action)
   - `ready: false` + manual fix only → BP-verification в Этапе 5 будет SKIP с пометкой; surface `recommended_workflow` token из ответа
   - tool недоступен (debug-hmr не зарегистрирован) → fallback к `mcp__1c-debug__*` (plain wrapper), либо BP-verification SKIP

4. Сопоставить результат с матрицей капабилити:

   | edt-mcp | 1c-mcp-crud | bsl-debugger | 1c-debug-hmr | Режим pipeline |
   |---|---|---|---|---|
   | ✓ | ✓ | ✓ | ✓ | **Full** — все 8 этапов работают как описано, Этап 5 включает BP-verification |
   | ✓ | ✓ | ✓ | ✗ | **Full (no-BP)** — все этапы работают, Этап 5 BP-verification SKIP (заметка в IMPLEMENTATION-PROGRESS) |
   | ✓ | ✗ | * | * | **Code-only** — Этапы 1, 3 (write), 4, 5, 7, 8. Этап 2 — только `validate_query` (синтаксис), без `execute_query`. Этап 6 — SKIP с пометкой "ожидает ручного тестирования". BP-verification доступна если debug-hmr ✓ |
   | ✗ | ✓ | * | * | **Read-only verify** — Этап 2 на данных, Этап 6 на данных. Запись кода невозможна (нет `write_module_source`) → STOP с просьбой запустить EDT |
   | ✗ | ✗ | * | * | **Read-only research** — только Этап 1 через fallback (см. ниже), сбор контекста. Запись и валидация невозможны → STOP перед Этапом 2 |

   `1c-debug-hmr` — ортогональная ось: его отсутствие НЕ блокирует pipeline, только отключает live BP-verification в Этапе 5 (см. §5.x). Smoke-test `scripts/smoke_test_implement_1c_task.py --json` отражает доступность в поле `mcp_health.debug_hmr`.

5. Если режим не **Full** — сообщить пользователю явно: какие серверы отсутствуют, какие этапы будут пропущены, что нужно поднять (EDT на `localhost:8765`, путь к `1c-mcp-crud` в `.mcp.json`, см. [16.6](../../../../docs/framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md)). Если debug-hmr unavailable но pipeline-mode иначе Full — это **Full (no-BP)**, не блокировать, только warn. Дождаться решения: продолжить в деградированном режиме или прервать.

6. Сохранить выбранный режим в IMPLEMENTATION-PROGRESS.md под заголовком `Pipeline mode: Full | Full (no-BP) | Code-only | Read-only verify | Read-only research`. Если debug-hmr ✓ — также записать `debug_session_id` (из `debug_health_check` response или `debug_connect` Этапа 5) в footer файла как `<!-- debug_session_id: <UUID> -->` (используется в §5.x regression diff на повторных прогонах той же задачи).
