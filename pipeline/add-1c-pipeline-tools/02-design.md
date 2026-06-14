# 02 Дизайн — реализация инструментов

## 1. BSL-форматер (`bsl_lint.py --format`)
- Новая функция `run_format(java, src_dir, config)` — `java -jar bsl-ls.jar --format --srcDir <dir> --configuration <cfg>` (format правит файлы **in-place** в srcDir).
- Флаг `--format` (action). Ветка в `main()` ДО диагностического пути:
  - **файл:** temp-copy → format в temp → сравнить байты before/after → если изменён, `write_bytes(after)` обратно в оригинал; отчёт «изменён / без изменений». Сохранение точных байт = сохранение BOM/кодировки 1С.
  - **каталог:** format in-place по target; отчёт «применён».
- Reuse существующих `find_java`/`_runnable`/`BSL_LS_JAR`/конфиг-генерации. Exit 0 (advisory); тех.сбой → 2.
- Wire: `implement-1c-task` Этап 4 — опц. шаг `python scripts/bsl_lint.py <module.bsl> --format` ПЕРЕД финальным статанализом (`--severity error`).
- **Безопасность:** форматер правит ровно переданный путь; для одиночного файла write-back только при реальном изменении (атомарно через write_bytes).

## 2. Coverage41C CI (`ci-1c.yml` job `coverage`)
- Единый `if:` = `vars.CI_1C_RUNNER_ONLINE == '1' && needs.yaxunit-tests.result == 'success'` (убрать дубль).
- `env`: `COVERAGE_BAT` → `...\coverage41c\Coverage41C-2.7.3\bin\Coverage41C.bat`; `EDT_LOCATION` ← `vars.EDT_LOCATION`; `IB_ALIAS` ← `vars.COVERAGE_IB_ALIAS`; `COVERAGE_OUT` → `build\reports\genericCoverage.xml`.
- Шаг проверки prerequisite: bat существует + `EDT_LOCATION` задан и существует → `available`; иначе `::warning::` + skip (не fail — `continue-on-error`).
- Запуск: `Coverage41C.bat start -i <IB> -u http://localhost:1550 -P <src> -o <out>` → vrunner YAxUnit → `Coverage41C.bat stop` (в `try/finally`, dbgs кладётся в finally).
- Upload artifact `genericCoverage.xml`. Ссылка на `tools/coverage41c/README.md` + ADR-020 в комментарии.

## 3. comol BSL-правила
- `architecture-research/cache/1c-bsl-coding-rules-comol.md` — факты (attributed `[web]` + URL), без выводов (per architecture-research Фаза 5).
- Указатель из `bsl-development` «Стандарты кода 1С» → cache-файл. Без копирования целиком.

## 4. sonar 1.18.1 — вывод (без кода)
DEFER **корректен**: 1.18.1 требует SonarQube ≥2025.4; у нас `lts-community` (9.9-era) + контейнер даже не запущен → апгрейд = СЕРВЕР, не jar. Уже сделанное (config_manager 1.16.1) — достаточно. Зафиксировать подтверждение в ADR-020.

## Тест-план (04)
- `bsl_lint.py --format` на копии реального BSL (idempotent: 2-й прогон = «без изменений»); диагностический режим не сломан (regression).
- `ci-1c.yml` — YAML-валидность (`yaml.safe_load`) + отсутствие дубля `if:`.
- code-verify (quality-review) на bsl_lint.py.

## Риски
- Форматер правит файлы → write-back только при изменении + только переданный путь (не вся конфигурация). dir-режим явно «in-place».
- bsl-ls `format` мог не принять `--configuration` → проверить тестом; при ошибке убрать флаг (format и без cfg работает с дефолтами).
