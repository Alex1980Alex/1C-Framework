# ADR-033: Remediation-этап по итогам SonarQube — pull-issues + scope на кастом + re-scan

**Дата:** 2026-06-21
**Статус:** accepted
**Исследование:** [../cache/1c-form-skd-spreadsheet-tooling-2026.md](../cache/1c-form-skd-spreadsheet-tooling-2026.md) (не профиль; контекст — гл. 43.7)
**Связь:** дополняет CI-слой Sonar (ADR-021) и [гл. 43.7](../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.7_АНАЛИЗ_ВСЕЙ_КОНФИГУРАЦИИ.md)

## Контекст

SonarQube подключён как **отчёт + quality gate** (CI `ci-1c.yml`, `run-sonar-analysis.ps1`): прогон → загрузка на сервер. Полный скан 2026-06-21 дал **57 268 BSL-issues** (BLOCKER 25 / CRITICAL 4 429 / MAJOR 12 473), QG=ERROR. Но **этапа исправления не было** — issues никуда не утекали обратно, QG=ERROR даже не блокировал CI (`run-sonar-analysis.ps1` ловит только падение сканера, не статус gate). Нужен воспроизводимый «этап исправления».

**Ключевое наблюдение (live worklist 2026-06-21):** топ-файлы BLOCKER/CRITICAL — **вендорная БСП** (`УправлениеДоступомСлужебный` 367, `УниверсальныйОбменДаннымиXML` 196, `КонвертацияОбъектовИБ` 177…); кастомный `гкс_` — лишь местами (`гкс_ОбменДаннымиXDTOСервер` 91). Top-правила = сложность (`CognitiveComplexity` 2186, `NestedStatements` 1056, `CyclomaticComplexity` 817) + безопасность/перф (`ExecuteExternalCode` 159, `CreateQueryInCycle` 76). [own, exp]

## Решение

Ввести remediation как **ОБЯЗАТЕЛЬНЫЙ паттерн через 1С-пайплайн** — команда/скилл [`/fix-sonar-task`](../../fix-sonar-task/SKILL.md): Sonar-issue **никогда не фиксится ad-hoc**, каждый реальный баг проходит analyze→implement→test→re-scan (обновление 2026-06-21 по требованию: «обработку багов настроить в обязательном порядке через пайплайн — это паттерн»). 4 шага. [own]

1. **Pull + приоритизация:** [`scripts/sonar_issues_pull.py`](../../../scripts/sonar_issues_pull.py) (создан, zero-dep urllib) — `/api/issues/search` → группировка по severity/правилу/файлу → worklist (severity → файл → строка) в `data/reports/sonar/`. Фокус: `--severities`, `--types BUG,VULNERABILITY`, `--path-contains` (кастом). Проверено live: 4454/4454 BLOCKER+CRITICAL.
2. **Scope-гейт (ОБЯЗАТЕЛЬНО):** править **только кастомный код** (`гкс_*`, `configuration/<JIRA>`) + **реальные дефекты** (BUG / VULNERABILITY / `CreateQueryInCycle` / `ExecuteExternalCode`). **НЕ трогать вендорную БСП** — она даёт ~90% issues, но это чужой код: правки сорвут обновление типовой и не стоят усилий. [exp]
3. **Fix через 1С-конвейер:** батч = один файл/модуль из worklist → содержательные (сложность/баги) через `/implement-1c-task` (BSL пишет Opus — [[Opus = Planner; BSL только Opus]]); тривиальные авто-фиксы (`MissingSpace`/`LineLength`/`Typo`) — пакетно через EDT-MCP. Делегируемое — на Z.AI, BSL — нет.
4. **Re-scan + verify:** повторный `run-sonar-analysis.ps1` → проверить **дельту по затронутым файлам** через `sonar_issues_pull.py` (issues по файлу → 0). Замкнуть на QG период «new code».

**Маппинг на пайплайн:** этап **4 Тестирование** (аудит: pull) → подаёт worklist в этап **3 Кодирование** (fix) → re-scan (этап 4). Запуск ручной/по решению, не на каждую задачу.

## Последствия

### Положительные
- Реальные дефекты (баги/безопасность/перф) приоритизированы и адресуемы пакетами по файлам. [own]
- Scope на кастом → не ломаем БСП, усилия туда, где они окупаются. [exp]
- `sonar_issues_pull.py` переиспользуем (CI-артефакт, локальный разбор, дельта-verify). [own]
- Re-scan замыкает петлю: видно, что фикс реально убрал issue. [own]

### Отрицательные / риски
- Ручной триггер (не авто) — нужно осознанно запускать. [own]
- 4 429 CRITICAL — в осн. **сложность** (рефакторинг, не быстрый автофикс); реалистично брать по приоритету (BUG/VULNERABILITY/перф сначала), а не «обнулить всё». [own]
- `--path-contains` с кириллицей (`гкс_`) из bash может манглиться — передавать через env/конфиг или ASCII-фильтр (`configuration`). [exp]

## Альтернативы (отклонены)
- **Авто-фикс ВСЕХ 57k issues** — отклонён: ~90% в БСП (чужой код), массовая правка сорвёт обновление типовой. [own]
- **Жёсткий QG-блокер CI сразу** (option «в») — отклонён ПОКА: текущий QG=ERROR из-за БСП-наследия завалит любой PR. Сначала baseline («new code» период) + scope на кастом, потом блокер на `new_violations` кастомного кода. [own]
- **Тащить issues в отдельную БД/борд** — избыточно; worklist в `data/reports/sonar/` + JSON достаточно. [own]

## Связанные файлы
- Создан: `scripts/sonar_issues_pull.py`, `scripts/sonar_setup_quality_profile.py` (профиль «1C BSL Way» 180/180), `.claude/commands/fix-sonar-task.md` + `.claude/skills/fix-sonar-task/SKILL.md` (обязательный паттерн-оркестратор)
- Существующие: `scripts/run-sonar-analysis.ps1`, `scripts/sonar_setup_quality_gate.py`, `scripts/sonar_sources.py`, `.github/workflows/ci-1c.yml`
- Док: `docs/framework documentation/43_ПАЙПЛАЙН_1С/43.7_АНАЛИЗ_ВСЕЙ_КОНФИГУРАЦИИ.md` (раздел «Этап исправления»)
- Отложено: жёсткий QG-блокер CI (option «в») — отдельным ADR после baseline
