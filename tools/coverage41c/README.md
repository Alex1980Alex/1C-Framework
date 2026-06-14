# Coverage41C — покрытие BSL-тестами (статус и запуск)

[Coverage41C 2.7.3](https://github.com/1c-syntax/Coverage41C) — замер покрытия BSL-кода тестами через
debug-протокол 1С (dbgs:1550) → `genericCoverage.xml` (читается SonarQube BSL-плагином). Точка интеграции
в 1С-пайплайне: **`implement-1c-task` Этап 6 / `/run-1c-tests`** (Тестирование) — обёртка вокруг прогона
YAxUnit/VA. Решение: **ADR-020**, roadmap `docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md`.

## ⚠ Состояние (проверено 2026-06-15)
- **Рабочий дистрибутив:** `Coverage41C-2.7.3/` (jar `lib/Coverage41C-2.7.3.jar` + launcher `bin/Coverage41C.bat` + `lib/*`).
- **`coverage41c.jar` в корне каталога — БИТЫЙ stub (9 байт «Not Found»), НЕ использовать.** Запуск только через `bin/Coverage41C.bat` (строит полный classpath).
- **JDK:** OK — Coverage41C 2.7.3 = class 55 (JDK 11), работает на 1C:EDT Axiom JDK 17.
- **БЛОКЕР (почему не стартует здесь):** требует EDT debug-плагины `com._1c.g5.v8.dt.debug.*.jar` на classpath — даже `--help` падает `NoClassDefFoundError: …RuntimeDebugClientException`. `bin/Coverage41C.bat` ищет их через `EDT_LOCATION` / `ring edt locations list`. На `C:\Program Files\1C\1CE` найдены только EDT components/JDK — НЕ `plugins/` полного 1C:EDT IDE.

## Разблокировка (что нужно для запуска)
1. **EDT_LOCATION** — каталог `plugins/` установленного **1C:EDT IDE** (содержит `com._1c.g5.v8.dt.debug.core_*.jar` + `…debug.model_*.jar`). Задать env `EDT_LOCATION=<EDT_IDE>\plugins` (или починить `ring`, он deprecated).
2. **dbgs:1550** — запущенный debug-сервер (обычно live: ragent `-debug -http`; проверка `Coverage41C.bat check -u http://localhost:1550`). На 2026-06-15 порт :1550 был live.
3. **Тест-прогон** YaXUnit/VA между `start` и `stop` (без него покрытие пустое).

## Поток (Этап 6 / run-1c-tests)
```
set EDT_LOCATION=<1C_EDT_IDE>\plugins
bin\Coverage41C.bat start -i <ИБ-alias> -u http://localhost:1550 -P <src> -o build\genericCoverage.xml
<прогон YaXUnit/VA — /run-1c-tests>
bin\Coverage41C.bat stop  -i <ИБ-alias> -u http://localhost:1550
# → genericCoverage.xml → SonarQube: -Dsonar.coverageReportPaths=build\genericCoverage.xml
```
Точные флаги: `Coverage41C.bat <cmd> --help`. ⚠ Одновременный attach отладчика (1c-debug-hmr) и Coverage41C к одному dbgs может конфликтовать — гонять coverage отдельно от debug-сессии.

## CI
`.github/workflows/ci-1c.yml` job `coverage` сейчас смотрит на битый `coverage41c.jar` и гейтится `CI_1C_RUNNER_ONLINE`. При появлении self-hosted 1С-runner: переключить на `bin/Coverage41C.bat` + задать `EDT_LOCATION`.
