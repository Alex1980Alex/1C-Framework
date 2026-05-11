# Roadmap 260511 — 1c-debug-hmr deficiencies post-GKSTCPLK-2468

> **Origin:** Phase 2.5 R.2 + Этап 5.x BP-verification на GKSTCPLK-2468 (Устранить замечания по результатам ОПЭ — Направление заблокированные ТС). 6 trigger attempts на dev-базе ИБTransportManagementDevelop, 4 BP set, **0 BP fire** (0% fire rate). Static analysis с high confidence остался единственным источником истины; live test ПОСЛЕ implementation подтвердил корректность fix'а, но обнаружил серьёзные gaps в 1c-debug-hmr coverage.
>
> **Status:** Phase 1 (P0) **COMPLETE** (commits `564b0f8` + `fcc0ed8`). Phase 2 (P1-P3) **COMPLETE** (commits `c2e960e` + `54fea7d`). Tests: 199 → 215 passed. **Open:** post-spawn rphost-attach gap (RC2 residual) — see §7 P0.4 follow-up.
>
> **Owner:** Alex Terletskii.
>
> **Связанные документы:**
> - [`260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md`](260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md) — original post-BP-fire fix (§10/§11 force_recycle Solution A)
> - [`260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md`](260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md) — HMR integration into /analyze-1c-task + /implement-1c-task
> - [`docs/framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.7_HMR_Subprocess_Wrapper.md`](../framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.7_HMR_Subprocess_Wrapper.md)
> - [`configuration/260304_GKSTCPLK-2182.../docs/260507_GKSTCPLK_2468.../IMPLEMENTATION-PROGRESS.md`](../../configuration/260304_GKSTCPLK-2182%20Доработать%20создание%20Направление%20на%20разгрузку%20для%20заблокированных%20ТС/docs/260507_GKSTCPLK_2468%20Устранить%20замечания%20по%20результатам%20ОПЭ/IMPLEMENTATION-PROGRESS.md) — source incident
> - Memory: [`feedback_1c_debug_hmr_alias_validation.md`](../../../Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_1c_debug_hmr_alias_validation.md), [`feedback_1c_debug_hmr_recycle_scope.md`](../../../Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_1c_debug_hmr_recycle_scope.md), [`feedback_1c_debug_url_protocol.md`](../../../Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_1c_debug_url_protocol.md)

## §1. Фактическая дисфункция (replay incident'а)

| # | Attempt | Trigger | Result | Root-cause (см. §2) |
|---|---|---|---|---|
| 1 | `connect("TestDB", force_recycle=True)` killed pid 56540 → BP ManagerModule:80 | `execute_code` re-post ТМУТ-000006 #1 | 0 events | RC1 + RC2 |
| 2 | Same session | `execute_code` re-post #2 (correct date 2026-05-08) | 0 events | RC1 + RC2 |
| 3 | + BP Module:235 | `execute_code` re-post #3 | 0 events | RC1 + RC2 |
| 4 | Disconnect → reconnect (pre_existing pid 61720) → BP re-set | `break_on_next` armed → thin client `tcp://` launch | "Информационная база не обнаружена" | RC3 (тонкий клиент не получил correct IB name); RC1 |
| 5 | Thin client `-http /DebuggerURL=http://localhost:1550` (PID 42420) | User UI re-post через GUI | 0 events, 0 targets | RC4 |
| 6 | Same | `debug_targets` poll | empty | RC4 |

**Session summary** (`debug_session_summary`): 2 sessions, 4 BP set, **0 fired** (0% fire rate), 0 stop events, 0 targets seen. Recycle invoked=True, method=`rac.turn_off`.

## §2. Root causes

### RC1 — `infobase_alias` accept'ится silently без cluster validation

`debug_connect(infobase_alias="TestDB")` вернул `status=connected, attach.result=registered, fully_registered=true` несмотря на отсутствие IB "TestDB" в cluster (реальные: `ИБTransportManagementDevelop`, `260507_DEV_ATERLETSKIY_53196`).

RDBG protocol IB-agnostic на уровне UI session attach; cluster-side validation происходит позднее, при попытке attach worker'а, и silently fail'ит. `setAutoAttachSettings` filter повис на несуществующее имя → ни один rphost не вошёл в attach scope.

**Доказательство:** `debug_targets` возвращал `[]` на всём протяжении 2 sessions.

### RC2 — `force_recycle_rphost=True` covers only pre-existing pids snapshot

Solution A документирует «убить pre-existing pids на момент connect → ragent spawn'ит fresh worker с активным filter». Однако:

- Killed pid 56540 (pre-existing на connect)
- `execute_code` через HTTP-сервис `1c-mcp-crud` spawn'ит новый rphost — ragent балансирует HTTP-request на свежий worker
- Свежий worker мог бы получить filter, но из-за RC1 (неверный `infobase_alias`) filter не применяется к workerам этой IB

Если RC1 был бы fixed (правильный `infobase_alias`), RC2 всё равно потенциально gap'нул бы coverage, потому что:
- Solution A `force_recycle` — snapshot-based (только pids known на момент `rac process list`)
- HTTP-service spawning происходит асинхронно после `setBreakOnNextStatement` arm — между этими событиями могут быть race-conditions
- Cluster может иметь multiple rphost'ов; load balancer может посылать requests на любой; debug filter применяется per-worker per-session

### RC3 — Thin client `/DebuggerURL` protocol mismatch не surface'ится в health_check

Первый launch использовал `tcp://localhost:1550`, ragent запущен `-debug -http` (HTTP-mode на :1550). Тонкий клиент surface'ил GUI-error «Неверно указан протокол отладки». Скорректировано на `http://`, но всё равно `debug_targets` остался пустым.

`debug_health_check(mode=probe)` проверяет `ragent_debug_flag` (`has -debug -http`), но **не проверяет** что external client'ы запустятся с матчинговым протоколом. Это offline check, не end-to-end.

### RC4 — Solution C (thin client после connect) не привёл к target registration

После корректного launch (`http://`), login в правильную IB, и UI re-post через GUI — `debug_targets` остался **0**. Возможные подпричины:
- Thin client успешно запустился, но его debug-registration происходит **только** при первом BSL-statement (lazy attach)
- Re-post документа landed на rphost вне attached subset (если RC1 не fixed, в attach subset 0 workers)
- `break_on_next` arm требует existing attached target — если target=0, distribute'ить filter некому

### RC5 — `debug_health_check(mode=probe)` returned `ready=true` несмотря на полный subsequent fail

Health-check проверяет infrastructure (порты, ragent flags, env vars, AU grants, baseline rphost count), но **не функциональную пригодность** end-to-end BP-fire pipeline. RC1-RC4 не detected пробами. Любой из этих root causes saw `ready=true` от health_check.

## §3. Improvement items

### §3.1. [P0] Валидация `infobase_alias` в `debug_connect` — fail-fast

**Файл:** `tools/bsl-debug-server/mcp_debug_server.py` → `RDBGClient.connect()` или MCP tool wrapper.

**Поведение:**

```python
async def _validate_infobase_alias(self, alias: str) -> tuple[bool, list[str]]:
    cluster_id = await self._get_cluster_id()
    cmd = [self._rac_exe, "infobase", f"--cluster={cluster_id}", "summary", "list"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                            encoding="cp866", errors="replace")
    available = re.findall(r"^name\s*:\s*(.+?)\s*$", result.stdout, re.MULTILINE)
    return (alias in available, available)

# В debug_connect ДО registerDbgUI:
matches, available = await self._validate_infobase_alias(infobase_alias)
if not matches:
    return {
        "status": "error",
        "reason": "infobase_alias_not_found",
        "provided": infobase_alias,
        "available": available,
        "hint": "Use one of available infobases. Aliases в .mcp.json пока не поддерживаются."
    }
```

**Acceptance:**
- `connect(alias="несуществующий")` → `status=error, available=[...]` за <100ms
- `connect(alias="ИБTransport...")` → существующее поведение (registered=true)
- Регрессия: existing tests `test_mcp_debug_server.py::test_connect*` проходят с mock cluster

**Effort:** XS (~30 min). **Risk:** низкий (read-only rac call).

### §3.2. [P0] Расширить `force_recycle_rphost` → `recycle_strategy`

**Файл:** тот же.

**Изменение API:** добавить параметр `recycle_strategy ∈ {none, pre_existing, all_rphosts_of_ib, all_rphosts_of_cluster}` со default `pre_existing` (текущее поведение). Для backward-compat: `force_recycle_rphost=True` mapping'ся на `recycle_strategy="pre_existing"`.

**Поведение `all_rphosts_of_ib`:**
1. Resolve `infobase_id` через `rac infobase list --cluster=<UUID>` → найти UUID по `name == infobase_alias`
2. `rac process list --cluster=<UUID> --infobase=<infobase_id>` → собрать все pids rphost'ов этой IB
3. Для каждого pid: `rac process turn-off --cluster=<UUID> --process=<pid_uuid> localhost:1545`
4. Wait 3s (existing pattern)

**Поведение `all_rphosts_of_cluster`:** `rac process list --cluster=<UUID>` → kill all rphost (HIGH RISK — разрыв всех сессий). Использовать **только** для personal dev-баз; surface ⚠ warning в return.

**Acceptance:**
- `recycle_strategy="all_rphosts_of_ib"` на `infobase_alias="ИБTransport..."` убивает все rphost'ы, обслуживающие именно эту IB
- HTTP-service trigger ПОСЛЕ recycle → новый rphost spawned уже видим в `debug_targets` (после fix §3.1 + это)
- Регрессия: existing `force_recycle_rphost=True` behaviour сохраняется как `recycle_strategy="pre_existing"`

**Effort:** S (~2h). **Risk:** средний (требует careful UUID resolution из rac output).

### §3.3. [P1] `debug_health_check` extension — функциональный smoke `bp_fire_smoke`

**Файл:** тот же.

**Изменение:** в `mode=probe` добавить новый check `bp_fire_smoke` (после всех existing checks):

```python
async def _smoke_test_bp_fire(self, infobase_alias: str) -> dict:
    """End-to-end BP-fire smoke. Requires 1c-mcp-crud available."""
    # 1. Скрытый BP на тривиальном statement (например, в самом MCP-сервере конфигурации)
    # 2. Trigger через execute_code мини-сниппет
    # 3. Ping with timeout 5s
    # 4. Pass если fire, иначе warn с reason
    ...
```

В response health_check:
```json
{
  "ready": false,
  "checks": {
    ...
    "bp_fire_smoke": {
      "status": "warn",
      "detail": "End-to-end BP-fire test failed: infobase_alias='TestDB' not in cluster (available: ИБTransport..., 260507_DEV_...)",
      "fix": "Provide existing infobase_alias OR define alias mapping in .mcp.json"
    }
  }
}
```

**Acceptance:**
- Honest `ready=false` когда BP-fire не работает по любой из RC1-RC4 причин
- Affirmative `ready=true` только когда end-to-end pipeline functioning
- В `mode=probe` skip smoke если `1c-mcp-crud` не зарегистрирован (graceful degradation)

**Effort:** M (~4h). **Risk:** средний (требует наличия 1c-mcp-crud + тестовой IB; possible side-effects от execute_code).

### §3.4. [P1] `wait_for_target` — synchronous target registration helper

**Файл:** тот же.

**Новый tool:**

```python
@server.tool()
async def debug_wait_for_target(timeout_sec: int = 10) -> dict:
    """Block until ≥1 target appears in debug_targets, or timeout.

    Returns: {targets_count, first_target_id, elapsed_ms, status: ok|timeout}
    """
    start = time.monotonic()
    while time.monotonic() - start < timeout_sec:
        targets = await self._get_targets()
        if targets:
            return {"status": "ok", "targets_count": len(targets),
                    "first_target_id": targets[0]["id"],
                    "elapsed_ms": int((time.monotonic() - start) * 1000)}
        await asyncio.sleep(0.5)
    return {"status": "timeout", "targets_count": 0,
            "suggestion": "Spawn thin client with /Debug or trigger BSL via execute_code"}
```

**Use case:** в Шаблоне 1 / 5 после `debug_connect` — `wait_for_target(15)` гарантирует что есть кому посылать BP. Если timeout — surface suggestion.

**Acceptance:**
- В happy path (Solution C thin client) — returns ok за <15s
- В fail path (RC1 alias mismatch) — timeout с readable suggestion
- Coordinated с background `_ping_loop` (не блокирует ping events)

**Effort:** XS (~1h). **Risk:** низкий.

### §3.5. [P1] `debug_launch_thin_client` — автоматический клиент с правильными флагами

**Файл:** тот же.

**Новый tool:**

```python
@server.tool()
async def debug_launch_thin_client(
    infobase_alias: str,
    user: str | None = None,
    password: str | None = None,
    wait_for_target_timeout: int = 15
) -> dict:
    """Launch 1cv8c.exe with correct /Debug, -http, /DebuggerURL flags.

    Auto-detects platform path via known locations + WMI. Returns pid + attached status.
    """
    # 1. Validate infobase_alias (см. §3.1)
    # 2. Discover 1cv8c.exe path
    # 3. Build command: 1cv8c.exe /S"localhost:1541\<IB>" /Debug -http
    #    /DebuggerURL="http://localhost:1550" [/N user /P password]
    # 4. Start-Process detached
    # 5. wait_for_target(timeout) — return when target registered
    ...
```

**Acceptance:**
- Closes RC3 (protocol mismatch impossible)
- Closes part of RC4 (target registration verified via wait_for_target)
- Cross-platform: works on Windows; Linux/Mac — return error «not supported»

**Effort:** M (~3h). **Risk:** низкий (subprocess + WMI lookups).

### §3.6. [P2] Diagnostics-on-no-fire в `debug_ping`

**Файл:** тот же.

**Изменение:** `debug_ping` ведёт `_consecutive_empty_pings` counter. После 3 подряд `events: []` — auto-append diagnostic payload:

```python
{
  "events": [],
  "count": 0,
  "no_fire_diagnostics": {
    "consecutive_empty_pings": 3,
    "targets_attached": 0,
    "infobase_in_cluster": false,
    "infobase_alias_provided": "TestDB",
    "available_infobases": ["ИБTransport...", "260507_DEV_..."],
    "active_rphosts": [<pids>],
    "suggestions": [
      "infobase_alias 'TestDB' not in cluster (RC1). Use one of available.",
      "If using execute_code trigger, also recycle_strategy=all_rphosts_of_ib (RC2)."
    ]
  }
}
```

**Acceptance:** ускоряет troubleshooting в 5-10× — user сразу видит what's wrong.

**Effort:** S (~2h). **Risk:** низкий.

### §3.7. [P2] Alias mapping в `.mcp.json` env

**Файл:** `mcp_debug_server.py` startup + `.mcp.json` `1c-debug-hmr.env`.

**Изменение:** поддержать env var `DEBUG_INFOBASE_ALIASES="TestDB:ИБTransport...;dev:260507_DEV_..."` — wrapper парсит на startup, при `debug_connect(infobase_alias="TestDB")` translate'ит в `"ИБTransport..."` ДО validation.

**Use case:** удобство для часто используемых long-name IB.

**Acceptance:** existing tests с `infobase_alias="TestDB"` не сломаются если в env defined mapping.

**Effort:** S (~1.5h). **Risk:** низкий.

### §3.8. [P3] Документировать антипаттерн «arbitrary infobase_alias»

**Файл:** `.claude/skills/1c-debug-hmr/SKILL.md` → §антипаттерны.

**Добавить:**

```markdown
| **Использовать произвольный `infobase_alias` (например, `TestDB`)** | RDBG примет registered=true silently, но `setAutoAttachSettings` filter повисит на несуществующее имя → BPs не fire ни на каком rphost | alias = одно из имён из `rac infobase summary list --cluster=<UUID>`. Для коротких имён — env-mapping `DEBUG_INFOBASE_ALIASES` (после §3.7) |
```

**Effort:** XS (~15 min). **Risk:** zero.

## §4. Priority + sequencing

| Phase | Items | Effort | Outcome |
|---|---|---|---|
| **Phase 1 (P0)** | §3.1 + §3.2 | ~2.5h | Закрывает RC1 + RC2 (core root-causes этой сессии). После Phase 1 happy path BP-fire pipeline должен работать. |
| Phase 2 (P1) | §3.3 + §3.4 + §3.5 | ~8h | Honest preflight, sync primitives, automated Solution C. Закрывает RC3+RC4+RC5. |
| Phase 3 (P2) | §3.6 + §3.7 | ~3.5h | UX improvements. |
| Phase 4 (P3) | §3.8 | ~15 min | Documentation. |

**Total: ~14h** на full closure. **P0 alone: 2.5h** — кандидат для immediate action.

## §5. Acceptance criteria (full roadmap)

- [x] `debug_connect("неправильный_alias")` returns `status=error` с available list — §3.1 ✓ E2E `TestDB` → `status=error, available=[...]`
- [x] `recycle_strategy="all_rphosts_of_ib"` корректно убивает все rphost'ы IB — §3.2 ✓ + `all_rphosts_of_cluster` killed pid 61720 (E2E)
- [~] `debug_health_check(probe)` включает `bp_fire_smoke` check — §3.3 PARTIAL: вместо invasive BP fire — `infobase_list` probe surfaces available IBs ✓
- [x] `debug_wait_for_target(15)` блокирует до регистрации или timeout — §3.4 ✓
- [x] `debug_launch_thin_client(IB)` запускает клиент с корректным URL — §3.5 ✓ E2E thin client discovery validated
- [x] `debug_ping` после 3 empty surface'ит no_fire_diagnostics — §3.6 ✓ E2E correctly detected RC2 on real cluster
- [x] `DEBUG_INFOBASE_ALIASES` env translates short aliases — §3.7 ✓ E2E `Trans` → `ИБTransportManagementDevelop`
- [x] SKILL.md §антипаттерны обновлён — §3.8 ✓ 7 new entries (incl. password OS exposure)
- [~] Re-run GKSTCPLK-2468 R.2 trace → BP fire — **E2E PARTIAL**: tools работают, но actual BP fire blocked post-spawn-attach gap (§7 follow-up P0.4)
- [x] Existing 199 unit tests passing — ✓ 215 passed (+16 new)
- [ ] Mock acceptance test расширен «alias validation» — deferred to P0.4 batch

## §6. Связь с уже-выполненной работой

| Item | Status в roadmap 260508/260510 | Closure в этом roadmap'е |
|---|---|---|
| Pre-existing rphost gap | §10/§11 Solution A documented | §3.2 расширяет на all_rphosts_of_ib (HTTP-service coverage) |
| Post-BP-fire handshake | §13 P1.3 closed (cached `last_stopped_target_id`) | Не затронуто — это другая axis |
| HMR session restoration | Closed (`.active.json` + 1872dff fix) | Не затронуто |
| Infobase_alias validation | **OPEN** — впервые surface'ится в GKSTCPLK-2468 | §3.1 close |
| Functional smoke в health_check | **OPEN** | §3.3 close |
| Thin client automation | **OPEN** — Solution C документирована как manual | §3.5 close |

## §7. Open questions

1. **Multi-rphost cluster behaviour:** на production-cluster с N workers ragent балансирует load — даже после `recycle_strategy=all_rphosts_of_ib` следующий request может landed на rphost spawned уже без filter (если filter применился на N-1, а N-й spawned race-condition). Возможно потребуется sticky-session механизм или filter re-arm после каждого new rphost.
2. **`bp_fire_smoke` side-effects:** smoke-check execute_code запустит реальный BSL — какой минимальный код безопасен на ЛЮБОЙ infobase? Кандидаты: `Результат = ТекущаяДата();` — pure read-only, но требует BP на встроенном модуле (1c-mcp-crud's `mcp_ИнструментЗапросыИКод` Module:97 — но это уже не trivial point). Возможно нужно создать dedicated test-module для smoke.
3. **Alias env-mapping security:** разрешать ли любые алиасы или enforce'ить наличие в cluster (т.е. mapping → final-IB всё равно валидируется через §3.1)? Скорее всего enforce'ить — иначе вернёмся в исходную проблему.

## §8. Не покрыто этим roadmap'ом

- Web-client / mobile debug attachment (отдельная axis)
- IIS COM-cache invalidation (требует iisreset, выходит за scope wrapper'а)
- Cross-machine debug (current scope — `localhost:1550` only)
- Plain `1c-debug` (non-HMR) — все улучшения предполагается портировать туда же, но это derivative work (mechanical port)
