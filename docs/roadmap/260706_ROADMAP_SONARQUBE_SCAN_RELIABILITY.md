# 260706 — Надёжность SonarQube-контура (скан → CE → verify → гейт)

> Разбор пяти инцидентов live-прогона 2026-07-06 (закрытие Sonar-гейта GKSTCPLK-2634 на машине DESKTOP-TNU600C)
> + аудит всего Sonar-инструментария репо. Все корни подтверждены по коду (file:line) и live-запросами к
> SonarQube CB 26.6 (`api/ce/activity_status`, `api/project_branches/list`, `.scannerwork/report-task.txt`).
> Связанные решения: ADR-021 (wiring), ADR-033 (remediation), ADR-034 (R6/R7), ADR-037 (mandatory гейт), ADR-042 (Sonar MCP), **ADR-048 (split по конфигурациям — P3)**.

## §1 Инциденты прогона 2026-07-06 и их корни

| # | Симптом (как проявилось) | Корень | Доказательство | Тяжесть |
|---|---|---|---|---|
| **I1** | Скан «упал» на первой же строке `Diagnostic computation error` (не-фатальный варнинг bsl-сенсора) при запуске с `*>&1`/`2>&1`; без редиректа проходит | PS 5.1: редирект stderr нативного exe оборачивает каждую stderr-строку в `NativeCommandError`; внутри скрипта действует `$ErrorActionPreference="Stop"` (`run-sonar-analysis.ps1:4`) → первая же stderr-строка терминирует | ps1:4 + ps1:61 (native `& $java -jar $cli`); повтор без редиректа — EXECUTION SUCCESS | Высокая (ломает любой лог-захват) |
| **I2** | Лог скана в UTF-16 (не грепается штатно) | PS 5.1 `>` = `Out-File` c дефолтом UTF-16 LE; `[Console]::OutputEncoding=UTF8` (ps1:5) на redirect-кодировку не влияет | семантика PS 5.1 | Низкая |
| **I3** | Повторный скан «прошёл» (exit 0), но фактически ничего не сканировал — источники/токен не найдены | Компаунд: (а) `$ProjectRoot = git rev-parse --show-toplevel` (ps1:8) **зависит от cwd** — из сабмодуля возвращает корень сабмодуля; (б) `.env` ищется от него (ps1:12) → токен не загружен → ветка «SONAR_TOKEN не задан» = **exit 0** (ps1:43–46); (в) `$LASTEXITCODE` helper-вызовов python (ps1:34, ps1:38) не проверяется, пустые `$sources` не гейтятся | ps1:8,12,34,38,43–46; `sonar_sources.py:25` сам якорится на своё расположение (`parents[1]`) — подводит именно ps1-обвязка | **Критическая** (тихий no-op под маской успеха) |
| **I4** | verify → ложный FAIL «анализ старше правок» сразу после успешного скана; через минуты — PASS без изменений | **Гонка финализации Compute Engine**: сканер завершается (exit 0) до того, как CE допишет анализ; `sonar_rescan_verify.py` берёт свежесть из `project_analyses/search?ps=1` (`last_analysis_dt`, verify:107–115) **без ожидания CE** → отдаёт предыдущий анализ → `scan_stale=True` (verify:299) | live: во время инцидента `project_analyses ps=1`=05:19:03 при `project_branches/list`=05:29:35; после финализации ps=2 показывает оба (05:29:35, 07:25:40); `ce/activity_status` доступен (`{"pending":0,"failing":0,"inProgress":0}`); сканер пишет `.scannerwork/report-task.txt` с `ceTaskId` — **не используется никем** | **Критическая** (ложный блок гейта ADR-037) |
| **I5** | Ad-hoc `curl` по файлу с кириллическим путём → `errors`/`total: None` | Ручное построение `componentKeys` без корректного URL-encode/формата ключа (`project:relative/path`); verify это уже решает (per-file `quote()` verify:180–186 + project-tree матчинг `_match_component` verify:238–249 + project-wide fallback) | транскрипт + verify:173–249 | Средняя (только диагностика руками) |

**Важно (вывод по целостности):** гейт ADR-037 в обоих инцидентах **не пропустил брак** — verify честно давал FAIL (stale) и не закрывался, пока не появился реально свежий анализ. Пострадала не корректность, а **время закрытия задачи** (часы вместо минут) и доверие к сигналам (ложный stale, обманчивый exit 0).

## §2 Дополнительные находки аудита (сверх инцидентов)

| # | Находка | Где | Риск |
|---|---|---|---|
| A1 | Helper-python зовётся голым `python` (ps1:34,38), тогда как QG-check — правильно через `.venv\Scripts\python.exe` (ps1:73). Store-alias → exit 49/чужое окружение ([[feedback-venv-python-windows]]) | run-sonar-analysis.ps1 | Средний |
| A2 | `_paged` cap: `page_size=500 × cap_pages=60` = 30k компонентов; проект ~14.4k файлов — сейчас ок, при росте >30k молчаливое усечение `analyzed` → ложное «не проанализирован» | sonar_rescan_verify.py:123–160 | Низкий (отложенный) |
| A3 | Freshness по fs mtime: пересохранение файла без изменений (mtime bump) после скана → ложный stale. Осознанный fail-safe компромисс — документировать | sonar_rescan_state.py:194–205 + verify:298–299 | Низкий |
| A4 | live: `qualityGateStatus=ERROR` на main — server new-code baseline вырожден (new≈total после полных сканов; `baseline_degenerate` verify:217–235 это детектит, гейт независим). Починка сервера — `api/new_code_periods/set` SPECIFIC_ANALYSIS **branch-level** на пре-change анализ ([[reference-sonar-changed-lines-gate]]) — сейчас руками | сервер / verify | Средний (шум soft-QG) |
| A5 | Конкурентность: сканер сам держит `.scannerwork/.sonar_lock` (два прогона из одного клона не пересекутся); CE-очередь сериализует. Отдельный лок не нужен — справочно | .scannerwork/ | — |
| A6 | Heap: дефолт `-Xmx6g` (ps1:58–59, верифицирован 2026-06-30); прогон 2026-07-06 шёл на 8g — но падение было от I1 (редирект), не от OOM. Дефолт не менять; env-override уже есть | run-sonar-analysis.ps1 | — |
| A7 | ~~MFM/Конфигурация детектится, но не сканируется → dead-block~~ **✅ РЕШЕНО 2026-07-06 (вариант а, решение пользователя):** MFM = свой проект **`utp-mfm`** — `sonar_sources.py STABLE_ROOTS += MFM/Конфигурация` (скан в mono сейчас, слепых зон нет), реестр `sonar_projects.py` += utp-mfm, `_is_config_bsl` детектит MFM (не исключает). Слепой зоны/dead-block больше нет | sonar_sources.py · sonar_projects.py · sonar_rescan_state.py | — |
| A8 | Ревью P3.A (2026-07-06): `_is_config_bsl` детектил `.bsl` в **`external/1c_mcp/src/`** (18) и **`tools/bsl-debug-server/src/`** (158 фикстур), которых нет в скане → латентный dead-block (класс MFM). **✅ закрыт сразу:** `_is_config_bsl` исключает `external/`/`tools/` (не продакшн-конфиги). Pre-existing (не регрессия P3.A) | sonar_rescan_state.py | — |
| A9 | `-Xmx6g` калибровался на {ИБ+SVETLY+260304}; теперь mono = {ИБ+SVETLY+MFM} — однократно подтвердить EXECUTION SUCCESS полного mono-прогона с MFM (heap) | run-sonar-analysis.ps1 | Низкий (операционный, до первого full-скана) |

## §3 Карта инструментария (кто что делает)

```
run-sonar-analysis.ps1 ──┬─ sonar_setup_quality_gate.py (G18, идемпотентно)
  (скан-оркестратор)     ├─ sonar_sources.py (G19, динамические корни; сам якорится на scripts/..)
                         ├─ scanner-cli (-Dsonar.projectBaseDir=<root>) → .scannerwork/report-task.txt (ceTaskId) → CE
                         └─ sonar_quality_gate_check.py (R6 CaYC; soft | SONAR_QG_HARD=1)
sonar_rescan_verify.py ──── ADR-037 дельта-verify (changed-lines) → .claude/cache/onec-sonar-rescan-state.json
  └─ shared/sonar_rescan_state.py (DRY-контракт: детект .bsl, diff-строки, parse_dt, evaluate)
onec-task-completion-stop.py / gate_policies.py ── Stop-гейт читает state (+parity-тесты)
sonar_issues_pull.py ── worklist MD/JSON/SARIF (+remediation_class) для /fix-sonar-task (ADR-033)
CI: .github/workflows/ci-1c.yml (bsl-analysis) · сервер: docker-compose.sonarqube.yml · setup-sonar.ps1
```

## §4 Дорожная карта исправлений

### P0 — ложные сигналы гейта (сделать первыми)

- **P0.1 CE-wait в verify (гонка I4). ✅ реализовано 2026-07-06.** `sonar_rescan_verify.py`: перед freshness-проверкой ждать финализацию CE — poll `GET /api/ce/activity_status?component=<project>` до `pending==0 && inProgress==0` (флаг `--wait-ce <сек>`, default 120, интервал 5с; таймаут → честный `scan_stale`-путь с подсказкой «CE ещё обрабатывает»). Freshness брать как **max**(`project_analyses/search?ps=1`, `project_branches/list.analysisDate`) — branches обновляется атомарнее.
  *Acceptance:* сценарий «скан exit 0 → немедленно verify» больше не даёт ложный stale (интеграционно: verify сразу после run-sonar-analysis.ps1 → PASS с первого раза).
  *Оценка:* 1–1.5 ч (код + unit на парсинг статусов + прогон).

- **P0.2 Fail-fast + cwd-независимый корень в ps1 (I3). ✅ реализовано 2026-07-06 (+P1.4 venv-python попутно).** `run-sonar-analysis.ps1`: (а) первичный якорь корня — `$PSScriptRoot\..` (скрипт лежит в `scripts/`), `git rev-parse` только как sanity/fallback + проверка `Test-Path "$ProjectRoot\scripts\sonar_sources.py"`; (б) отсутствие токена = **exit 2** с красным сообщением (не exit 0); reachability-DOWN оставить exit 0 (осознанный локальный комфорт), но печатать маркер `SCAN-SKIPPED`; (в) после helper-python проверять `$LASTEXITCODE`, пустые `$sources` → exit 2.
  *Acceptance:* запуск из каталога сабмодуля даёт либо корректный скан, либо громкий exit≠0; «exit 0 без скана» невозможен кроме явного `SCAN-SKIPPED` (сервер DOWN).
  *Оценка:* ~1 ч.

### P1 — операбельность и следующая петля

- **P1.1 CE-handoff по `report-task.txt` в ps1 (канонический механизм).** После сканера прочитать `.scannerwork/report-task.txt` → poll `api/ce/task?id=<ceTaskId>` до `SUCCESS|FAILED|CANCELED` (таймаут ~10 мин) → печать `analysisId`/статуса; `FAILED` → exit 1. Осознанно **не** использовать `sonar.qualitygate.wait=true` — он связал бы exit-код сканера с QG (у нас QG сознательно soft, R6) и имеет свой 300с-таймаут.
  *Acceptance:* ps1 завершается только после финализации CE; verify после него никогда не видит in-progress.
  *Оценка:* ~1 ч. (После P1.1 `--wait-ce` в verify становится страховкой для ручных прогонов.)

- **P1.2 Встроенный `-LogFile` (I1+I2).** ps1-параметр `-LogFile <path>`: скрипт сам пишет UTF-8-лог (native-safe: `cmd /c "... > log 2>&1"` для java-вызова либо `Start-Process -RedirectStandardOutput/-RedirectStandardError`), вокруг native-блока локально `$ErrorActionPreference='Continue'` (контроль по `$LASTEXITCODE`, ps1:66 уже есть). Вызывающим **никогда** не требуется PS-редирект.
  *Acceptance:* `run-sonar-analysis.ps1 -LogFile x.log` даёт полный UTF-8 лог; запуск с внешним `*>&1` больше не роняет скрипт (EAP локализован).
  *Оценка:* 0.5–1 ч.

- **P1.3 Диагностический подрежим verify (I5).** `sonar_rescan_verify.py --show-file <rel>`: печатает разрешённый `component_key` + unresolved issues файла (та же машинерия `_match_component`/`file_issue_lines`) — оператору не нужен ручной curl с кириллическим ключом.
  *Acceptance:* `--show-file "TransportManagementDevelop_SVETLY/.../ManagerModule.bsl"` → ключ + список issue без ошибок кодировки.
  *Оценка:* ~0.5 ч.

- **P1.4 `.venv`-python для helper-вызовов (A1).** ps1:34,38 → `& "$ProjectRoot\.venv\Scripts\python.exe"` (как ps1:73), fallback на `python` при отсутствии venv.
  *Оценка:* 0.2 ч.

### P2 — гигиена и отложенное

- **P2.1 Cap-лог `_paged` (A2):** при `len(out) >= page_size*cap_pages` печатать «⚠ усечение»; поднять cap до 100 стр.
- **P2.2 Скрипт baseline (A4):** `scripts/sonar_set_new_code_baseline.py --to-latest-before <ISO|analysisId>` — обёртка `api/new_code_periods/set` (branch-level SPECIFIC_ANALYSIS, принимается ТОЛЬКО branch-level — project-level set = тихий no-op, проверять `/list`); убирает ручной шаг починки вырожденного baseline и шум soft-QG ERROR.
- **P2.3 Документация:** гл. 43.9.9 (статанализ) — раздел «Операционные ловушки» (I1–I5: не редиректить ps1; запуск из корня/якорь; CE-асинхронность; --show-file), синхронно с [[reference-sonar-changed-lines-gate]].
- **P2.4 ADR-042 (Sonar MCP) — переоценка после P0/P1:** hand-rolled urllib-клиент в verify растёт; если появится ещё ≥2 API-потребителя — вернуться к adoption-решению MCP-сервера Sonar (сейчас zero-dep оправдан для Stop-хука).

### P3 — Разделение Sonar-проекта по конфигурациям (принято 2026-07-06, [ADR-048](../../.claude/skills/architecture-research/adr/048-sonar-project-split-per-configuration.md))

> Перенесено из §5 решением пользователя. Монопроект → `utp-ib` / `utp-svetly` / `utp-mfm` (**три** проекта; approve-поправки 2026-07-06: `configuration/<JIRA>` **исключён** из Sonar-скоупа и детекта гейта целиком — папки ведения задач; **`MFM/Конфигурация` = свой проект `utp-mfm`**, A7 вар.а — сканируется, слепых зон нет). Ключевой выигрыш: гейтовый скан = только затронутая конфигурация + **per-project `scan_stale`** (правка SVETLY не требует свежести ИБ) + ожидаемая починка SCM blame (projectBaseDir = один git work-tree).

- **P3.A0 Исключение `configuration/` (✅ реализовано 2026-07-06 при approve):** `sonar_sources.py` (`GROWING_PARENTS=[]`, механизм оставлен — возврат одной строкой) + `sonar_rescan_state._is_config_bsl` (префикс-фильтр, гейт не детектит) + 2 unit-теста + докнота 43.9.9. Действует в обоих режимах (сужение скоупа, не часть split-флага). Осознанный риск: будущие правки `.bsl` в `configuration/**/src/` гейт не проверит (принято пользователем).
- **P3.A Код (opt-in, default OFF):**
  - **P3.A.registry ✅ реализовано 2026-07-06:** реестр `scripts/sonar_projects.py` (единственная точка маппинга `path → {key, root}` = `utp-ib`/`utp-svetly`/`utp-mfm`; `project_for_path`/`roots`/`--list-json`) + A7 закрыт (MFM в скоупе, `sonar_sources STABLE_ROOTS += MFM`, детект без исключения) + 7 unit (`test_sonar_projects.py`) + правка `test_sonar_rescan_state`. 28/28, ruff, code-verify PASS.
  - **P3.A.wiring (осталось):** `run-sonar-analysis.ps1 -Project <key|all>` (цикл, per-project `projectKey`/`projectBaseDir`/`sources=.`) + `sonar_rescan_verify.py` (группировка изменённых по проектам через `project_for_path`, per-project freshness/issues, state аддитивно `projects:{}`) + обвязка (QG-setup/QG-check/issues_pull циклы). Env `SONAR_SPLIT_PROJECTS` (0 = legacy бит-в-бит).
  *Acceptance:* при флаге OFF поведение неотличимо от текущего; при ON verify правки SVETLY требует свежести только `utp-svetly`. *Оценка (wiring):* 2–3 ч.
- **P3.B Сервер:** первый скан каждого проекта (провижининг, фоном) → pin new-code baseline per project (P2.2 скрипт — пререквизит) → smoke verify на живой правке → проверить SCM Publisher (blame ожидаемо оживает). *Пререквизит: P0.1/P0.2* (те же файлы; без CE-wait smoke флапает). *Оценка:* 1–1.5 ч.
- **P3.C Переключение:** `SONAR_SPLIT_PROJECTS=1` дефолт в `.env`, CI-цикл (`ci-1c.yml`), docs (гл. 43.9.9 + ноты fix-sonar-task/implement-1c-task), старый проект `upravlenie-transportom-plk` — archived read-only (история worklist), удаление ≥30 дней отдельным решением. *Оценка:* ~1 ч.

**Матрица приоритетов:** P0.1+P0.2 устраняют оба «критических» корня (ложный stale + тихий no-op) ≈ 2–2.5 ч; P1 целиком ≈ 2–3 ч; P2 — по мере касания; **P3 (ADR-048) ≈ 5.5–7 ч отдельным пакетом после P0**. Активная часть без P3 ≈ **4–5.5 ч**.

**Порядок внедрения:** P0.1 → P0.2 → **P3.A → P3.B → P3.C** (решение пользователя приоритизирует split; P1.1/P1.2 полезны, но P3.B закрывает ту же боль per-project) → P1.3/P1.4 → P2. Каждый пункт — через пайплайн (правки Python/ps1 = обычный code-verify цикл; это инфраструктура фреймворка, не 1С-код — Sonar-гейт ADR-037 на неё не распространяется, обычный `code-verify` PASS обязателен).

## §5 Что НЕ делаем (и почему)

- ~~Разделение Sonar-проекта на 3 конфигурации~~ — **пересмотрено 2026-07-06 (решение пользователя): ДЕЛАЕМ** → фаза **P3** + [ADR-048](../../.claude/skills/architecture-research/adr/048-sonar-project-split-per-configuration.md). Прежние контр-аргументы сняты дизайном: единая точка маппинга ключей = реестр `sonar_projects.py`, dual-mode `SONAR_SPLIT_PROJECTS` (rollback = флаг), re-baseline закрывает P2.2-скрипт.
- **`sonar.qualitygate.wait=true`** — остаётся отклонённым: связывает exit-код сканера с QG-политикой (у нас QG сознательно soft, R6 ADR-034) + свой 300с-таймаут; ожидание CE решается P1.1/P0.1 без QG-сцепки.
- **Свой lock поверх `.sonar_lock`** — остаётся отклонённым: сканер уже сериализует прогоны из одного клона (A5); в split-режиме локи per-project (`.scannerwork` в корне каждого конфига) — коллизий нет.

## §18 Прогресс

### 2026-07-06 — P3.A.registry + A7 решён (utp-mfm, вар.а); P0 доказан live

- **A7 (вар.а, решение пользователя):** MFM/Конфигурация = свой проект **`utp-mfm`** (сканировать, слепых зон нет). Реестр `scripts/sonar_projects.py` (utp-ib/utp-svetly/utp-mfm, `project_for_path`/`roots`/`--list-json`); `sonar_sources STABLE_ROOTS += MFM` (скан в mono сейчас); `_is_config_bsl` детектит MFM (не исключает). 7 unit + правка rescan-state теста; 28/28, ruff, code-verify PASS.
- **P0 доказан live:** `wait_ce` idle→True за 0.04с, `branches_analysis_dt`==`analyses ps=1` (max-freshness), 404-fast-path мгновенный, сервер up. Осталось P3.A.wiring (ps1 `-Project` + verify per-project).

### 2026-07-06 — P0 реализован (wait-ce + fail-fast ps1); попутно BOM-фикс ps1

- **P0.1:** `sonar_rescan_verify.py` — `wait_ce()` (poll `ce/activity_status` до idle, `--wait-ce` default 120с, 404→fast-path R1) + freshness = max(`project_analyses`, `project_branches/list`). **P0.2:** `run-sonar-analysis.ps1` — якорь `$PSScriptRoot\..` + sanity, FATAL exit 2 (токен/sources/helper'ы), `SCAN-SKIPPED`-маркер, venv-python (`P1.4` ✅), guard `KEY=` (R4).
- **Попутная находка:** ps1 был UTF-8 БЕЗ BOM → PS 5.1 читал cp1251, байт 0x94 из `—` в НОВЫХ двойных строках = типографская `”` (валидный делимитер PS) → parse error. Добавлен BOM + тест-инвариант (R3).
- Верификация: 27/27 unit (+7 P0, +BOM-инвариант), ruff clean, ParseFile OK, live smoke; code-verify reviewer **PASS** (advisory R2/R5 — noted: multi-branch max при появлении веток фильтровать isMain; интеграционный тест main-wiring — при следующем заходе).

### 2026-07-06 — Approve ADR-048 с поправкой: configuration/ исключён; P3.A0 реализован

- Пользователь одобрил дизайн с уточнением: вместо `utp-cfg-<JIRA>` авто-проектов — `configuration/<JIRA>` исключается из Sonar-скоупа И детекта гейта целиком (ведение задач, не код). Реестр = 2 проекта (`utp-ib`, `utp-svetly`).
- **P3.A0 реализован:** `sonar_sources.py` GROWING_PARENTS=[] + префикс-фильтр в `_is_config_bsl` + 2 unit-теста + докнота 43.9.9. Pipeline `sonar-scan-reliability`: дизайн approved.

### 2026-07-06 — Разделение Sonar-проекта по конфигурациям ПРИНЯТО (ADR-048, §5 → P3)

- Отказ §5 пересмотрен пользователем → новая фаза P3: реестр `scripts/sonar_projects.py`, ключи `utp-ib`/`utp-svetly`/`utp-cfg-<JIRA>`, dual-mode `SONAR_SPLIT_PROJECTS`, миграция A (код, opt-in) → B (провижининг+baseline+smoke) → C (флип дефолта, archive старого проекта).
- Ожидаемые выигрыши: скан = только затронутая конфигурация, per-project `scan_stale`, вероятная починка SCM blame (один work-tree). Пререквизит — P0. Порядок внедрения обновлён (P3 сразу после P0).

### 2026-07-06 — Роадмап создан (разбор инцидентов SQ-прогона + аудит инструментария)

- Пять инцидентов live-прогона (GKSTCPLK-2634 гейт) разобраны до корней с file:line; все корни подтверждены кодом и live-API (`ce/activity_status`, `project_branches/list`, `report-task.txt` с ceTaskId).
- Аудит: +6 доп. находок (A1–A6), карта инструментария, матрица P0–P2 (активная часть ≈ 4–5.5 ч).
- Ключевой вывод: гейт ADR-037 брак не пропускал — инциденты били по времени закрытия и доверию к сигналам (ложный stale I4, тихий no-op exit 0 I3). P0 закрывает оба.
