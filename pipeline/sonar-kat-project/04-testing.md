# Тестирование: Sonar-проект utp-kat

## Функциональная проверка правок (уровень 1)
- `sonar_projects.py --list-json` содержит utp-kat ✓
- `project_for_path("TransportManagementDevelop_KAT/Конфигурация/src/...bsl")` → `("utp-kat", root, "src/...")` ✓ (comp_rel = путь внутри конфига)
- `projects()`/`roots()` включают utp-kat ✓
- `sonar_sources.py --list` содержит KAT-корень ✓
- compile-smoke обоих .py ✓

## Провижининг + baseline-скан
`run-sonar-analysis.ps1 -Project utp-kat -LogFile ...`:
- 2103 `.bsl` обработаны BSL Core Sensor; 7243 preprocessed; 2 языка ✓
- `ANALYSIS SUCCESSFUL` (id=utp-kat), `EXECUTION SUCCESS`, `CE analysis SUCCESS` ✓
- Heap `-Xmx6g`, без OOM; прогон ~1.5 мин ✓

## Серверная проверка
- `/api/projects/search?projects=utp-kat` → проект TRK, lastAnalysisDate 2026-07-22T23:03 ✓
- `components/tree?qualifiers=FIL` → 2505 файлов ✓
- measures: ncloc 640124, files 2505; baseline issues 48 blocker / 5126 critical / 66833 total
  (ЛЕГАСИ первого скана — НЕ гейтит: Clean-as-You-Code по изменённым строкам + baseline_degenerate) ✓
- `sonar_rescan_verify.py --project utp-kat --show-file src/Catalogs/Валюты/.../Module.bsl`
  → `component_key: utp-kat:src/...`, 6 unresolved issues ✓ (боевой resolve компонента подтверждён)

## Unit-тесты
- `test_sonar_projects.py` — обновлён ассерт (4 проекта) + `test_project_for_path_maps_kat` (comp_rel=src/...); саботаж-проба: без utp-kat map KAT → None ✓
- `test_sonar_rescan_state.py` — +KAT в `test_is_config_bsl_detects_registry_configs_incl_mfm` (парный инвариант детект↔скоуп) ✓
- Прогон: **31 passed**

## code-verify (уровень 2, behavior-preservation)
Ревьюер-субагент (read-only): **PASS** по всем 8 пунктам — аддитивно, нет шадоинга KAT↔SVETLY
(расхождение `_KAT`/`_SVETLY` на 1-м символе после общего префикса), нет hardcode «3 проекта»,
все N-местные потребители (ps1 foreach, sorted(groups)) масштабируются, парный инвариант соблюдён.

## Известный минорный нюанс (не дефект правки)
`--show-file` в split-режиме требует КОНФИГ-относительный путь (`src/...`), а не repo-относительный
— пред-существующее свойство диагностического подрежима, общее для всех split-проектов. Боевой
гейт (`_run_split`) берёт comp_rel из `project_for_path`, поэтому не затронут.
