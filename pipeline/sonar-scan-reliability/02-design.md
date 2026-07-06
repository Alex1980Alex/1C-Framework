# 02 — Дизайн: SQ-контур (надёжность + split по конфигурациям)

Этап 2 пайплайна `sonar-scan-reliability`. Дизайн-артефакты (single source):

- **[ADR-048](../../.claude/skills/architecture-research/adr/048-sonar-project-split-per-configuration.md)** — разделение Sonar-монопроекта по конфигурациям (реестр `sonar_projects.py`, ключи `utp-*`, dual-mode `SONAR_SPLIT_PROJECTS`, миграция Phase A/B/C, rollback = флаг). Статус: **accepted** (решение пользователя 2026-07-06).
- **[Roadmap 260706 §4](../../docs/roadmap/260706_ROADMAP_SONARQUBE_SCAN_RELIABILITY.md)** — P0 (CE-wait verify, fail-fast ps1) + P1 (report-task poll, -LogFile, --show-file, venv-python) + P2 (гигиена) + **P3 = ADR-048** с acceptance-критериями per-пункт.

**Порядок кодирования (этап 3):** P0.1 → P0.2 → P3.A → P3.B → P3.C → P1.3/P1.4 → P2.

**Approve: 2026-07-06 (пользователь), с поправкой** — `configuration/<JIRA>` исключён из Sonar-скоупа и детекта гейта целиком (вместо `utp-cfg-<JIRA>` авто-проектов); реестр = 2 проекта (`utp-ib`/`utp-svetly`). Поправка внесена в ADR-048 + roadmap P3; P3.A0 (исключение) реализован сразу.
