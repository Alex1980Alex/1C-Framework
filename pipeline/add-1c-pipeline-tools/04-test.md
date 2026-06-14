# 04 Тестирование

## Формат-режим (живое исполнение + unit)
- **Live (bsl-ls):** CLI `format` probe → rc=0, `--configuration` принят, отступы добавлены. `bsl_lint.py <file> --format` run1=«изменён», run2=«без изменений» (idempotent); после R1/R3-hardening happy-path сохранён (rc=0 → 3 таба).
- **Regression:** диагностический режим (`--severity warning`) не сломан (нашёл `UnusedLocalVariable`).
- **Unit:** [`tests/unit/test_bsl_lint_format.py`](../../tests/unit/test_bsl_lint_format.py) — 4/4 PASS (write-back контракт: changed+rc0→write, unchanged→skip, changed+rc!=0→skip, tmp-missing→warn). Marker `unit` (в CI-гейте). ruff чисто (RUF100-fix).
- **code-verify:** quality-review субагент → **PASS** (R1/R3/R2 применены, R4=этот unit-тест).

## Coverage41C CI
- YAML-валидность + **отсутствие дублей ключей** проверены (`yaml.load` strict dup-check) → выявил и починил 2-й дубль `if:` в `allure-report`.
- Запуск job невозможен здесь (нет runner/EDT IDE/dbgs) — gate отрабатывает skip+`::warning::` (проверено логикой).

## comol cache
- `_index.json` re-parse OK (27 тем); cache-файл создан с frontmatter + `[web]`-атрибуцией.

## sonar
- Проверено: `docker ps` — sonar-контейнер не запущен; image `sonarqube:lts-community`. DEFER корректен.

**Итог:** все 3 инструмента реализованы и проверены; sonar — обоснованный DEFER.
