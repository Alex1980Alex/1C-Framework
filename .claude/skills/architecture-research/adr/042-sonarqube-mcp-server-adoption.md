# ADR-042: Adopt SonarQube MCP Server (on-demand via lazy-mcp)

**Дата:** 2026-06-25
**Статус:** accepted
**Исследование:** [cache/sonarqube-mcp-server-2026.md](../cache/sonarqube-mcp-server-2026.md)
**Связано:** ADR-021/033/034/037 (Sonar QG/remediation/гейт), lazy-mcp (гл.26)

## Контекст
SonarQube Community Build 26.6 + BSL-плагин уже дают анализ 1С-кода; доступ к результатам — через
zero-dep скрипты `scripts/sonar_*.py` (pull/QG/rescan). SonarSource выпустил **официальный MCP-сервер**
(`sonarsource/sonarqube-mcp`, 29 tools), который вписывается в нашу MCP-архитектуру и даёт агенту
нативный доступ + триаж issues, чего скрипты не покрывают.

## Решение
Принять **SonarQube MCP Server** как **on-demand** сервер в `lazy-mcp` (категория `code-quality`).
Запуск — через launcher [`scripts/sonar_mcp_launch.py`](../../../scripts/sonar_mcp_launch.py): **единый источник
секрета** — читает `SONAR_TOKEN`/`SONAR_HOST_URL` из gitignored `.env` (наши имена) и маппит в
`SONARQUBE_TOKEN`/`SONARQUBE_URL` (имена образа); `localhost`→`host.docker.internal` (контейнер). Скрипты
`sonar_*.py` **остаются** как deterministic fallback + CI (zero-dep, без Docker).

## Smoke (живой, на нашем CB, 2026-06-25)
- Образ `sonarsource/sonarqube-mcp` запущен, **подключился** к `host.docker.internal:9000` (Instance: SonarQube Server), **auth нашим токеном OK**, 29 tools.
- `tools/call search_sonar_issues_in_projects` (projects=upravlenie-transportom-plk, severities=BLOCKER) → **isError=false**, вернул **BSL-issue** `bsl-language-server:ForbiddenMetadataName` (BLOCKER, OPEN). Подтверждено: **BSL-issues видны через MCP на Community Build**.
- API-уровень (тот же, что оборачивает MCP): 5155 BLOCKER+CRITICAL, top-правила `bsl-language-server:*`.

## Последствия
### Положительные
- Нативный MCP-доступ агента: `search_sonar_issues_in_projects`, `get_project_quality_gate_status`,
  `show_rule`, `change_sonar_issue_status` (**триаж FP прямо из агента** — раньше руками), и др.
- On-demand (lazy-mcp) — нет always-on стоимости; токен из `.env` (single-source, не дублируется).
### Отрицательные / caveats
- Часть tools (`run_advanced_code_analysis`, `search_dependency_risks`, context augmentation) — Cloud/Enterprise
  2025.4+, на Community недоступны (issues/QG/rules — работают).
- `analyze_code_snippet` (локальный анализ) — образ без bundled-анализаторов (languages: []); нам не нужен
  (используем server-issue tools).
- Зависимость от Docker (контейнер на запрос). Скрипты `sonar_*.py` остаются для no-Docker/CI.

## Альтернативы
- **Только скрипты `sonar_*.py`** (статус-кво). Отклонено: нет нативного триажа/агентского доступа.
- **Always-on MCP в `.mcp.json`**. Отклонено: lazy-mcp on-demand дешевле (Sonar нужен не в каждой сессии).
- **SonarQube Cloud / SonarLint IDE**. Отклонено: self-host (Cloud не наш); SonarLint BSL-поддержка не подтверждена.

## Связанные файлы
- `scripts/sonar_mcp_launch.py` (launcher), `.mcp/lazy-mcp-config.json` (категория code-quality + serverDef sonarqube).
- `scripts/sonar_issues_pull.py` / `sonar_quality_gate_check.py` / `sonar_rescan_verify.py` (fallback/CI).
- Док: гл.43.9.9 (статанализ), гл.26 (lazy-mcp).

## Коррекция (2026-06-25, deep launch-audit)
Реальный конфиг lazy-mcp-прокси — `infra/lazy-mcp/config/registry.yaml` (грузит server.py), НЕ `.mcp/lazy-mcp-config.json` (vestigial, 0 ссылок → удалён). sonarqube (+category code-quality) и context7 внесены в registry.yaml; прокси: 10 категорий / 25 серверов.

## Переоценка после P0/P1 (2026-07-06, roadmap 260706 P2.4)
urllib-клиент в `sonar_rescan_verify.py` вырос (P0/P1: `wait_ce`, `branches_analysis_dt`, `show_file`, `_paged` cap). **Решение подтверждено: `sonar_*.py` остаются zero-dep, НЕ мигрируют на Sonar MCP.** Причина: verify исполняется в контекстах БЕЗ MCP — CI-джоб (`ci-1c.yml`), `run-sonar-analysis.ps1`, а результат читает Stop-гейт `onec-task-completion-stop` (headless). Sonar MCP (Docker on-demand в сессии Claude) там недоступен. Порог миграции (≥2 новых Sonar-API-потребителя ВНЕ gate/CLI-пути) НЕ достигнут — новые функции обслуживают тот же гейт/диагностику. Sonar MCP остаётся для **интерактивного триажа** (search/QG/change-status в сессии). Пересмотреть, если появится потребитель Sonar-API в самой сессии.
