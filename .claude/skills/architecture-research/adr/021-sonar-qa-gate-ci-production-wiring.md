# ADR-021: SonarQube QA-gate — продакшен-проводка в CI (G17/G18/G19)

**Дата:** 2026-06-15
**Статус:** accepted
**Исследование:** [1c-bsl-tooling-ecosystem-2026.md](../cache/1c-bsl-tooling-ecosystem-2026.md) + live-верификация (roadmap [260614](../../../../docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md) раздел «Глубокий анализ S.1–S.6»)
**Связан с:** [ADR-020](020-phase9-1c-tooling-adoption-verified.md) (Phase 9 adoption; sonar там был DEFER → RESOLVED установкой 2026-06-15)

## Контекст

SonarQube разблокирован 2026-06-15: поднят Community Build 26.6.0.123539 + плагин communitybsl 1.18.1
(180 BSL-правил), live-скан 428 BSL verified. Глубокий анализ (roadmap S.5) выявил 3 нетехнических
решения + 1 техупрощение, нужных для продакшен-проводки QA-gate в CI Этапа 4 (Тестирование):

- **G17** — хостинг sonar для CI: `ci-1c.yml` job `bsl-analysis` шлёт на `localhost:9000` (self-hosted),
  но это не зафиксировано; шаг хрупкий (bundled scanner-JRE = LFS-указатель 130 байт → сломан; стейл-пути `D:\1C-FW`).
- **G18** — на сервере только дефолтный «Sonar way» (new-code, baseline пуст → всегда OK); на legacy-конфиге
  29 697 issues → гейт нерепрезентативен без настройки.
- **G19** — `sonar.sources=configuration` указывает на ~пустой dir (1 .bsl); реальный конфиг —
  `ИБTransportManagementDevelop/Конфигурация` (2103 .bsl, = projectKey `upravlenie-transportom-plk`).
- **Техупрощение** — плагин 1.18.1 гоняет bsl-language-server **встроенно** (Sensor BSL Core, verified без
  внешнего отчёта) → внешний `sonar.bsl.languageserver.reportPath` + отдельный CI-шаг «Run BSL LS» избыточны как sonar-вход.

## Решение

### G17 — self-hosted runner + локальный SonarQube (НЕ SonarCloud) [own]
1С-конфиг = **проприетарный код заказчика** → в облако (SonarCloud) не загружаем (supply-chain/приватность).
CI BSL-анализ исполняется на self-hosted Windows-runner'е (`[self-hosted, windows-11, 1c]`) с **локальным**
SonarQube-контейнером (`docker/docker-compose.sonarqube.yml`, CB 26.6) на `localhost:9000` + `SONAR_TOKEN` repo-secret.
**Проводка (robust):** шаг sonar получает (а) reachability-gate (`/api/system/status` → чистый skip, если сервер down —
паттерн runner-gate/`EDT_LOCATION`-gate), (б) запуск через **scanner-cli jar** (НЕ `.bat` с битым bundled-JRE):
любой доступный java (EDT Axiom 17 / system) для CLI-bootstrap + **server-JRE-provisioning** тянет JDK 21 для
bsl-сенсора (class 65; обязательно — verified-блокер); (в) пути `D:\1C-FW` → `C:\1С-Framework`.

### G18 — quality gate «1C BSL Way», Clean-as-You-Code (new-code) [web: SonarSource Clean-as-You-Code]
Кастомный гейт на проект `upravlenie-transportom-plk`, условия **только на NEW-code** (legacy 29k долга —
grandfathered, не блокирует): new reliability rating = A (нет новых bugs), new security rating = A (нет новых vulns),
new security hotspots reviewed = 100%, new maintainability rating = A, new duplicated lines density ≤ 3%.
Coverage-условие (new-code coverage ≥ 60%) — **отложено** до разблокировки Coverage41C (genericCoverage.xml).
**Воспроизводимость:** гейт создаётся скриптом `scripts/sonar_setup_quality_gate.py` (API: создать gate + условия +
назначить проекту) — repo-tracked, идемпотентно, любой SonarQube-инстанс восстановим. Применён + verified на live-сервере.

### G19 — `sonar.sources` ДИНАМИЧЕСКИ (источники растут) + drop внешнего bsl-report [own]
Источники **РАСТУТ** (новые `configuration/<JIRA>` сабмодули, доп. конфиги) → НЕ хардкодим один путь.
`scripts/sonar_sources.py` открывает все корни с .bsl на момент скана (главный конфиг
`ИБTransportManagementDevelop/Конфигурация` + все `configuration/*`; расширяемо через `STABLE_ROOTS`/
`GROWING_PARENTS`), runner/CI передают `-Dsonar.sources=<comma-list>` → новый корень с .bsl
авто-подхватывается без правки конфигов; пустые/невыгруженные сабмодули отбрасываются. `sonar-project.properties`
`sonar.sources` = **статический fallback** (главный конфиг) для ручного `sonar-scanner` без обёртки. CI checkout —
`submodules: recursive` (источники = сабмодули). Внешний `sonar.bsl.languageserver.reportPath` **убран**
(плагин анализирует .bsl встроенно — verified); CI-шаг «Run BSL LS» — только human-readable artifact.

## Последствия

**Положительные:** QA-gate встаёт в Этап 4 как реальный кандидат «единого вердикта» (закрывает часть G9/G11);
гейт не блокирует на legacy-долге (Clean-as-You-Code); скан нацелен на реальный конфиг; CI-шаг robust к
down-серверу и битому bundled-JRE; gate воспроизводим (config-as-code). Все 4 закрывают G16–G19 из roadmap.

**Отрицательные / границы:** CI-job остаётся **gated off** (`CI_1C_RUNNER_ONLINE`) до регистрации self-hosted
runner'а → шаг sonar **не верифицируем e2e в CI сейчас** (верифицирован локально: gate-setup + re-scan).
Локальный bsl-сенсор требует **живого сервера** (JRE-provisioning) ИЛИ установленного JDK 21 — на runner'е без
доступа к серверу не запустится (документировано). Coverage-половина вердикта Этапа 4 ждёт Coverage41C (BLOCKED, ADR-020).

## Альтернативы

- **SonarCloud (отклонено):** внешний хостинг проприетарного 1С-конфига — privacy/supply-chain; платно для private.
- **Гейт на абсолютных метриках (отклонено):** заблокировал бы любой PR из-за 29k legacy-долга; Clean-as-You-Code — индустриальный стандарт brownfield.
- **Оставить внешний bsl-report (отклонено):** дублирует встроенный сенсор плагина → двойной анализ/риск double-count.
- **Материализовать bundled scanner-JRE через `git lfs pull` (отклонено как основное):** хрупко (зависит от LFS-выгрузки на runner'е); scanner-cli + server-provisioning надёжнее и уже verified.

## Связанные файлы

`scripts/sonar_setup_quality_gate.py` (new), `scripts/sonar_sources.py` (new, G19 динамика),
`sonar-project.properties`, `.github/workflows/ci-1c.yml`, `scripts/run-sonar-analysis.ps1`,
`docker/docker-compose.sonarqube.yml`, `src/bsl/sonar/config_manager.py`.
Будущий **ADR-022** — дивергенция кодирования/гейтов G6/G7 (сдвинут с 021).
