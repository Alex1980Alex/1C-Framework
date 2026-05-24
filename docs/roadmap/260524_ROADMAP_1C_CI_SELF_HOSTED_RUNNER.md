# Roadmap 260524 — 1C CI self-hosted runner activation

**Дата:** 2026-05-24
**Trigger:** Audit показал что `ci-1c.yml` jobs (BSL Static Analysis, YAxUnit, BDD) вечно QUEUED на всех PR'ах.

## §1 Problem

`ci-1c.yml` workflow требует `runs-on: [self-hosted, windows-11, 1c]` runner. У репо **нет self-hosted runner'а** с этими labels — поэтому jobs ждут вечно в QUEUED:
- BSL Static Analysis (BSL LS + SonarQube)
- YAxUnit Tests
- BDD Tests (Vanessa Automation)

**Impact:** на каждом PR (даже non-BSL) появляются 3 вечно-QUEUED checks → noise в `gh pr view`, false alarm в Monitor, нельзя использовать как required gate.

## §2 Root cause

`ci-1c.yml` `pull_request:` trigger **БЕЗ `paths:`** фильтра → запускается на каждый PR. При этом jobs зависят от среды:
- `ONEC_PATH: 'C:\Program Files\1cv8\8.3.27.1859\bin'` (1C platform)
- `OSCRIPT_PATH: 'C:\Tools\OneScript\bin\oscript.exe'`
- `VRUNNER_PATH: 'C:\Tools\OneScript\bin\vrunner.bat'`
- `IB_CONNECTION: '/SKOMPUTER\testdb1c'` (SQL Server 1С infobase)
- TestDB обработка для VA BDD scenarios
