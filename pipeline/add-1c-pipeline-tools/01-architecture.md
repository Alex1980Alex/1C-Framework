# 01 Планирование — добавление инструментов в 1С-пайплайн

**Контекст:** продолжение Phase 9 (roadmap 260614). После EVAL/DEFER-разбора решено добавить 3 кандидата,
не требующих внешних зависимостей/инфры сверх имеющейся.

## Объём (3 кандидата + 1 проверка)
1. **BSL-форматер** — bundled bsl-ls умеет `format` (подтверждено `--help`: `format, -f, --format`). Добавить
   режим `--format` в [`scripts/bsl_lint.py`](../../scripts/bsl_lint.py) → автоформат в `implement-1c-task` Этап 4. Без новых зависимостей.
2. **Coverage41C CI-проводка** — job `coverage` в [`ci-1c.yml`](../../.github/workflows/ci-1c.yml) смотрит на битый 9-байт
   `coverage41c.jar` + неверный вызов + дубль `if:`. Переписать на `Coverage41C-2.7.3/bin/Coverage41C.bat` + `EDT_LOCATION`-gate
   (реальный блокер из ADR-020). Активируется при self-hosted runner + полном 1C:EDT IDE.
3. **comol/cursor_rules_1c** — не инструмент, набор BSL-правил. Выжать стандарты в cache (attributed) + указатель из `bsl-development`.
4. **sonar 1.18.1 (проверка, НЕ реализация)** — подтвердить корректность DEFER.

## Факты разведки (this session)
- `bsl-language-server.jar` (0.22) поддерживает `format` subcommand (CLI `--help`).
- SonarQube = `docker/docker-compose.sonarqube.yml` → image `sonarqube:lts-community` (9.9-era LTA), **контейнер не запущен**.
- `config_manager.py` placeholder уже исправлен (1.0.0→1.16.1, прошлый коммит).
- ci-1c.yml job `coverage` (строки 164-233): битый jar + дубль `if:` (172 и 174).
