# 03 Кодирование

## 1. BSL-форматер ✅
- [`scripts/bsl_lint.py`](../../scripts/bsl_lint.py): `run_format()` + `_do_format()` + флаг `--format` + ранняя ветка в `main()` + docstring/usage.
- Safety (R1/R3 из code-verify): одиночный файл — write-back ТОЛЬКО при `after != before` И `rc == 0`; при `rc!=0`+отличиях оригинал НЕ перезаписан; при пропаже temp-файла — `::warning::` в stderr, оригинал не тронут. Каталог — in-place, честное сообщение «прогон завершён».
- Wire: [`implement-1c-task/SKILL.md`](../../.claude/skills/implement-1c-task/SKILL.md) Этап 4 шаг 0 (v2.8.1) + указатель из [`bsl-development/SKILL.md`](../../.claude/skills/bsl-development/SKILL.md).

## 2. Coverage41C CI ✅
- [`.github/workflows/ci-1c.yml`](../../.github/workflows/ci-1c.yml) job `coverage`: `Coverage41C.bat` вместо битого jar; `EDT_LOCATION`/`COVERAGE_IB_ALIAS`-gate; start/stop в `try/finally`; artifact `genericCoverage.xml`.
- Bonus-fix: дубль ключа `if:` в jobs `coverage` И `allure-report` (затирал runner-gate → QUEUED-навсегда) → единый combined `if:`.

## 3. comol BSL-правила ✅
- Кеш [`1c-doc-research/cache/external-bsl-ai-coding-rules-comol.md`](../../.claude/skills/1c-doc-research/cache/external-bsl-ai-coding-rules-comol.md) (`[web]`, license: public-domain) + `_index.json` (27 тем) + указатель из `bsl-development`.

## 4. sonar 1.18.1 — вывод (без кода)
DEFER подтверждён: SonarQube `lts-community` (9.9-era), контейнер не запущен → апгрейд сервера, не jar.

## Документация
ADR-020 (formatter follow-on + Coverage41C CI-wiring done + sonar verified + comol) + roadmap §18.
