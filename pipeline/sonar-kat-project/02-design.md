# Дизайн: Sonar-проект `utp-kat` (реализация ADR-048)

## Контекст (по фактам, проверено)

Появилась 4-я конфигурация `TransportManagementDevelop_KAT/Конфигурация` (2103 `.bsl`, база
`TransportManagementDevelop_KAT`). Особенность: **не сабмодуль** — закоммичена прямо в главный
репо (ИБ/SVETLY/MFM — сабмодули).

**Почему это срочно, а не «nice to have»:**
- Детект гейта `sonar_rescan_state._is_config_bsl` — **путь-ориентированный** (любой `.bsl` под
  `/src/`, кроме `configuration/`/`external/`/`tools/`), НЕ привязан к реестру (P3.B — будущее).
  KAT в главном репо под `/src/` → правки KAT **уже детектятся** как продакшн-1С-код.
- split-режим **включён** (`SONAR_SPLIT_PROJECTS=1` в `.env`; `utp-ib/utp-svetly/utp-mfm`
  провижинены на сервере).
- В split `sonar_rescan_verify._group_by_project` мапит через `project_for_path`; файл вне
  реестра → `unmapped` → **fail-closed** «не сопоставлен проекту реестра».
- Итог: первая же правка `.bsl` в KAT → гейт `onec-task-completion-stop` даёт **неустранимый
  блок** (сканировать нечего — проекта нет). Добавление в реестр закрывает дыру.

Сервер: SonarQube 26.6 UP на `localhost:9000`; `utp-kat` **не существует**.

## Решение (ADR-048 «расширение = одна запись»)

1. **`scripts/sonar_projects.py`** `PROJECTS += {key:"utp-kat", root:"TransportManagementDevelop_KAT/Конфигурация", name:"УправлениеТранспортомНаПЛК (KAT)"}`.
   Это ЕДИНСТВЕННО-необходимая правка: даёт `project_for_path` (verify перестаёт fail-closed'ить
   KAT), `projects()`/`roots()` (скан-цикл ps1 `--list-json` подхватит), детект/скан-скоуп сходятся.
2. **`scripts/sonar_sources.py`** `STABLE_ROOTS += "TransportManagementDevelop_KAT/Конфигурация"`.
   В split не используется (ps1 берёт реестр), но держит парный инвариант «скан-скоуп ↔ mono»
   в согласии — на случай mono-фоллбэка. Поведение split бит-в-бит не меняет.
3. **Провижининг + baseline**: `run-sonar-analysis.ps1 -Project utp-kat -LogFile <log>`.
   SonarQube авто-создаёт проект на первом скане (штатно, отдельный API не нужен). ps1 ждёт
   финализацию CE по `report-task.txt`. Heap `-Xmx6g` (проверен на 3 конфигах разом → на одном
   KAT с запасом; RAM машины 61.6 ГБ).
4. **Verify heap/скан**: EXECUTION SUCCESS + CE SUCCESS в логе + проект в `/api/projects/search`
   с файлами; опционально `sonar_rescan_verify.py --project utp-kat --show-file <любой KAT .bsl>`.

## Границы / что НЕ делаем

- НЕ трогаем детект `_is_config_bsl` (P3.B — отдельная проводка реестра в детект; сейчас
  path-shaped детект + реестр в verify уже дают корректный результат для KAT).
- НЕ включаем/меняем `SONAR_SPLIT_PROJECTS` (уже 1).
- НЕ правим сам конфиг KAT.
- Baseline будет вырожденным (первый скан → new≈total) — это ОЖИДАЕМО и НЕ гейтит
  (`baseline_degenerate`-детект + гейт считает дельту по diff-строкам, не по inNewCodePeriod).

## Риски

| Риск | Митигация |
|---|---|
| Скан KAT конфликтует с открытым в EDT KAT | Нет: сканер читает диск read-only |
| OOM на скане | Heap 6g верифицирован; KAT — один конфиг, меньше нагрузки чем mono×3 |
| Кириллический путь конфигурации в ps1 | Реестр отдаётся `--list-json` UTF-8 байтами; ps1 `ConvertFrom-Json` (проверенный путь utp-mfm с кириллицей уже работает) |
| SCM blame (KAT в главном репо, не сабмодуль) | projectBaseDir=корень конфига внутри рабочего дерева главного репо → git blame работает от главного репо; для baseline не критично |

## Проверка (Тестирование)

- `sonar_projects.py --list-json` содержит utp-kat; `project_for_path("TransportManagementDevelop_KAT/Конфигурация/src/X.bsl")` → `("utp-kat", ...)`.
- `sonar_sources.py --list` содержит KAT-корень.
- Скан: лог `EXECUTION SUCCESS` + `CE analysis SUCCESS`.
- Сервер: `utp-kat` в `/api/projects/search`, `components/tree?qualifiers=FIL` > 0 файлов.
- code-verify (behavior-preservation) на обеих Python-правках.
