# Sonar CI production wiring (G17/G18/G19)

Задача: «сделай» — довести sonar до продакшен-проводки в CI (3 решения из roadmap 260614 S.5).
Slug: `sonar-ci-production-wiring`

## 1. Планирование
Grounded-исследование: CI-job `bsl-analysis` уже на self-hosted+localhost (G17 по сути выбран, но хрупкий:
bundled-JRE=LFS-указатель, стейл D:\1C-FW); сервер — только дефолтный gate (G18); `sonar.sources=configuration`
= ~пусто, реальный конфиг `ИБTransportManagementDevelop/Конфигурация` 2103 .bsl (G19). ADR-№: 021 (next sequential).

## 2. Дизайн → ADR-021 (accepted)
3 решения + техупрощение. **Правка пользователя на лету:** источники РАСТУТ → G19 = динамическая дискавери, не хардкод.

## 3. Реализация
- `scripts/sonar_setup_quality_gate.py` (G18) — gate «1C BSL Way» Clean-as-You-Code, идемпотентно, repo-tracked.
- `scripts/sonar_sources.py` (G19) — динамическое открытие BSL-корней (главный конфиг + растущие configuration/<JIRA>).
- `sonar-project.properties` (G19) — sources=fallback + drop внешнего bsl-report (плагин встроенный).
- `.github/workflows/ci-1c.yml` (G17) — robust sonar-шаг (reachability + scanner-cli + provisioning JDK21 + пути D:→C: + submodules).
- `scripts/run-sonar-analysis.ps1` (G17) — локальный runner под ту же логику (auto-root).
- `_index.json` — ADR-021 зарегистрирован; roadmap S.6/§18 + сдвиг G6/G7→ADR-022.

## 4. Тестирование (verified вживую)
- gate setup: «1C BSL Way» создан, 6 new-code условий, назначен проекту, new-code=previous_version (API-verified).
- discovery: оба корня (главный + configuration/260304), пустой 260416 отброшен.
- **e2e:** `run-sonar-analysis.ps1` → reachability✓ + gate✓ + dynamic sources✓ + полный скан 7215 файлов
  `ANALYSIS SUCCESSFUL` → **Quality Gate OK** (baseline, Clean-as-You-Code grandfather).
- статика: ruff passed, py_compile OK, _index.json valid, ci-1c.yml YAML valid, PS parse OK.

Границы: CI-job gated off (нет runner) → sonar-шаг не e2e-в-CI (verified локально). Coverage-условие deferred (Coverage41C BLOCKED).
