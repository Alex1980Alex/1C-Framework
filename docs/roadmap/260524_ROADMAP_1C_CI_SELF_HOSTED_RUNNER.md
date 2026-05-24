# Roadmap 260524 — 1C CI self-hosted runner activation

**Дата:** 2026-05-24
**Trigger:** Audit показал что `ci-1c.yml` jobs (BSL Static Analysis, YAxUnit, BDD) вечно QUEUED на всех PR'ах.

## §1 Problem

`ci-1c.yml` workflow требует `runs-on: [self-hosted, windows-11, 1c]` runner. У репо **нет self-hosted runner'а** с этими labels — поэтому jobs ждут вечно в QUEUED:
- BSL Static Analysis (BSL LS + SonarQube)
- YAxUnit Tests
- BDD Tests (Vanessa Automation)

**Impact:** на каждом PR (даже non-BSL) появляются 3 вечно-QUEUED checks → noise в `gh pr view`, false alarm в Monitor, нельзя использовать как required gate.
