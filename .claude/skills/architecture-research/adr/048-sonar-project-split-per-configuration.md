# ADR-048: Разделение Sonar-монопроекта на проекты по конфигурациям

**Дата:** 2026-07-06
**Статус:** accepted (решение пользователя 2026-07-06; отменяет отказ §5 [roadmap 260706](../../../../docs/roadmap/260706_ROADMAP_SONARQUBE_SCAN_RELIABILITY.md)). **Approve 2026-07-06 с поправкой:** `configuration/<JIRA>` исключён из Sonar-скоупа и детекта гейта ЦЕЛИКОМ (вместо `utp-cfg-<JIRA>` авто-проектов) — там ведение задач, не код.
**Исследование:** live-аудит SQ-контура — roadmap 260706 §1–§3 (инциденты прогона GKSTCPLK-2634, live-API `ce/activity_status`/`project_branches/list`/`report-task.txt`)
**Связь:** ADR-021 (wiring), ADR-037 (mandatory гейт), ADR-034 R6 (QG soft), ADR-042 (Sonar MCP), [[reference-sonar-changed-lines-gate]]

## Контекст

Один Sonar-проект `upravlenie-transportom-plk` объединяет 3+ корня конфигураций (~14.4k файлов:
`ИБTransportManagementDevelop/Конфигурация`, `TransportManagementDevelop_SVETLY/Конфигурация`,
растущие `configuration/<JIRA>/…`). Модель Sonar — снапшот всего проекта: частичный скан невозможен
(файлы вне `sonar.sources` считаются удалёнными и переписывают снапшот). Следствие: гейт ADR-037
(«анализ свежее правок») на правку ОДНОГО файла в ОДНОЙ конфигурации требует полного скана всех трёх
(минуты + 6g heap), а `scan_stale` в verify общий — правка SVETLY требует «свежести» и по ИБ.
Дополнительно multi-root скан через сабмодули полностью ломает SCM blame (SCM Publisher 0/4758 —
newness живёт на issue creationDate). Первоначальный отказ (§5 roadmap 260706: «стоимость > выгоды»)
пересмотрен пользователем: частота гейтовых сканов растёт (ADR-037 default-ON на каждую 1С-задачу).

## Решение

Разделить монопроект на **проект-на-конфигурацию**, реестр-центрично, с dual-mode переключателем:

1. **Реестр `scripts/sonar_projects.py`** (единственный источник истины, stdlib-only — импортируем и
   из verify, и из ps1 через `--list-json`):
   - Стабильные: `utp-ib` ← `ИБTransportManagementDevelop/Конфигурация`; `utp-svetly` ←
     `TransportManagementDevelop_SVETLY/Конфигурация`; **`utp-mfm` ← `MFM/Конфигурация`**
     (УправлениеМатериальнымиПотоками; A7 вар.а, решение пользователя — сканируется, слепых зон нет).
   - `configuration/<JIRA>/…` — **ИСКЛЮЧЕНЫ из Sonar-скоупа И из детекта гейта целиком**
     (approve-поправка пользователя 2026-07-06: это папки ведения задач — ТЗ/доки/исторические
     дампы, живой код не ведётся). Реестр = **три** проекта. Возврат конфигурации в скоуп —
     одна запись в `PROJECTS`. `external/`/`tools/` (не продакшн-конфиги: BSL-расширение MCP,
     тест-фикстуры) — тоже вне детекта гейта (A8, ревью P3.A).
     ~~Вариант `utp-cfg-<цифровой префикс>` авто-проектов~~ — отклонён пользователем.
   - API: `projects()`, `roots()`, `project_for_path(rel) → (key, root, rel_in_root) | None`, CLI `--list`/`--list-json`. **✅ реализован** ([`scripts/sonar_projects.py`](../../../../scripts/sonar_projects.py)).
2. **Скан:** `run-sonar-analysis.ps1 -Project <key|all>` — цикл по реестру; на проект:
   `-Dsonar.projectKey=<key>`, `-Dsonar.projectBaseDir=<корень конфига>`, `-Dsonar.sources=.`.
   `projectBaseDir` = корень сабмодуля → сканер работает в одном git work-tree → **ожидаемая починка
   SCM blame** (верифицировать в Phase B по логу SCM Publisher). Ключ компонента становится
   `<key>:<путь-внутри-конфига>`.
3. **Verify/гейт:** `sonar_rescan_verify.py` группирует изменённые `.bsl` по `project_for_path`;
   per-project `analyzed_file_keys`/`last_analysis_dt`/issue-запросы; **`scan_stale` считается только
   по затронутым проектам** (правка SVETLY больше не требует свежести ИБ — главный операционный
   выигрыш вместе с ~3× меньшим сканом). Схема state сохраняет текущие top-level поля (агрегат) +
   добавляет `projects: {key: {last_analysis, stale}}` — потребитель `sonar_rescan_state.evaluate`
   правок не требует.
4. **Dual-mode:** env `SONAR_SPLIT_PROJECTS` (unset/0 = legacy-монопроект бит-в-бит; 1 = split).
   Переключение дефолта — только в Phase C. Rollback = снять флаг (до Phase C старый проект жив).
5. **Обвязка:** `sonar_setup_quality_gate.py` — назначение QG «1C BSL Way» всем проектам реестра;
   `sonar_quality_gate_check.py` / `sonar_issues_pull.py` — `--project` + цикл; CI `ci-1c.yml` — цикл
   по реестру; после первого скана каждого проекта — pin new-code baseline (SPECIFIC_ANALYSIS,
   branch-level — скрипт P2.2 roadmap 260706 становится пререквизитом).

### Миграция (фазы)

- **Phase A0 (реализовано при approve 2026-07-06):** исключение `configuration/` —
  `sonar_sources.py` (`GROWING_PARENTS=[]`, механизм оставлен) + `sonar_rescan_state._is_config_bsl`
  (префикс-фильтр) + 2 unit-теста + докнота 43.9.9. Действует в ОБОИХ режимах (это сужение скоупа,
  не часть split-флага).
- **Phase A (код, opt-in, default OFF):** реестр (2 проекта) + ps1 + verify/state + обвязка +
  unit-тесты (маппинг путей, группировка, legacy-паритет). ≈ 2.5–3.5 ч (упростилось без utp-cfg).
- **Phase B (сервер):** первый скан каждого проекта (провижининг; фоном) → pin baseline per project →
  smoke verify по живой правке → проверка SCM Publisher (blame). ≈ 1–1.5 ч. **Пререквизит: P0.1/P0.2
  roadmap 260706** (CE-wait + fail-fast ps1 — те же файлы, и без CE-wait smoke будет флапать).
- **Phase C (переключение):** `SONAR_SPLIT_PROJECTS=1` дефолт (.env), CI-матрица, docs (гл. 43.9.9,
  fix-sonar-task/implement-1c-task ноты), старый проект — archived read-only (история worklist),
  удаление — отдельным решением ≥30 дней. ≈ 1 ч.

## Последствия

### Положительные
- Гейтовый скан = только затронутая конфигурация (~минуты → десятки секунд на малых; SVETLY-правка
  не сканирует ИБ) [own, live-замеры Phase B].
- Per-project `scan_stale` — устраняет класс «чужая конфигурация задерживает мой гейт» [own].
- Ожидаемая починка SCM blame (один work-tree на скан) → честная new-code атрибуция на сервере [own→verify Phase B].
- Скоуп сужен до живых конфигураций: `configuration/<JIRA>` (ведение задач) исключён из скана
  И детекта гейта [решение пользователя] — G19 (авто-подхват JIRA-конфигов) сознательно упразднён.

### Отрицательные / компенсации
- Если правка `.bsl` однажды случится в `configuration/<JIRA>/**/src/` — гейт ADR-037 её НЕ проверит
  (осознанный риск, принят пользователем: там ведение задач). Компенсация: возврат корня = одна
  строка реестра + снятие префикс-фильтра `_is_config_bsl` (одна точка).
- Ключи компонентов меняются во всех потребителях → компенсируется реестром как единственной точкой
  маппинга + dual-mode (старые ключи живы до Phase C).
- Первый скан ×N проектов → одноразовая стоимость; baseline на каждый — закрывается скриптом P2.2.
- История/worklist старого проекта — archived read-only, ссылки не бьются.
- QG-статусы теперь per-project (дашборды/ссылки обновить в docs).

## Альтернативы (отклонены)

1. **Status quo (монопроект)** — отклонён решением пользователя: время гейта растёт с частотой задач.
2. **`sonar.inclusions`/частичный скан в том же проекте** — невозможно: отсутствующие файлы
   трактуются удалёнными, снапшот переписывается [web: модель Sonar].
3. **Monorepo-фича Sonar** — Developer Edition+; у нас Community Build [web].
4. **Ветка-на-конфигурацию** — искажает семантику веток/baseline/PR-логики; хак [own].
5. **`utp-cfg-<JIRA>` авто-проекты для `configuration/<JIRA>`** (исходный дизайн этого ADR) —
   отклонено пользователем на approve 2026-07-06: в этих папках ведение задач (ТЗ/доки/исторические
   дампы), живой код не ведётся → исключены из скоупа целиком (см. поправку в Решении).

## Связанные файлы

`scripts/sonar_projects.py` (новый), `scripts/sonar_sources.py` (A0 ✅), `scripts/run-sonar-analysis.ps1`, `scripts/sonar_rescan_verify.py`,
`.claude/hooks/shared/sonar_rescan_state.py` (схема state — аддитивно), `scripts/sonar_setup_quality_gate.py`,
`scripts/sonar_quality_gate_check.py`, `scripts/sonar_issues_pull.py`, `.github/workflows/ci-1c.yml`,
`docs/framework documentation/4_МЫШЛЕНИЕ/4.4_ПАЙПЛАЙН_1С/43.9.9_СТАТАНАЛИЗ_И_КАЧЕСТВО.md`,
roadmap `docs/roadmap/260706_ROADMAP_SONARQUBE_SCAN_RELIABILITY.md` (P3).
