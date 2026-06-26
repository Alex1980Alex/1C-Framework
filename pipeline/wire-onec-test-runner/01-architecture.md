# 01 Планирование — Wire mcp-onec-test-runner (jar v0.5.1)

## Проблема
После фикса `.env`/`_dotenv` раннер всё равно не стартовал: jar v0.5.1 (alkoleft) конфигурируется
**только Spring-профилем `app.*`**, а launcher слал несуществующие CLI-флаги `--v8-path`/`--connection-string`
→ Spring их игнорировал → `basePath=null` → APPLICATION FAILED TO START → `✘ failed`.

## Цель
Запустить `mcp-onec-test-runner` против изолированной тест-ИБ так, чтобы он стартовал, отвечал на
MCP и прогонял YAxUnit-тесты (Smoke `ЮТТПримерТест`).

## Ключевые вводные (из байткода jar + живых проб)
- `ApplicationProperties`: format / **base-path (NotNull)** / source-set / connection / platform-version / tools.
- source-set **обязан** содержать запись типа **CONFIGURATION** (иначе `IllegalArgumentException: Требуется source set типа CONFIGURATION`).
- Раннер несёт build-pipeline (`DesignerBuildAction`: LoadConfigFromFiles + UpdateDBCfg) → **сам собирает в подключённую ИБ** → нужна изоляция от рабочей ИБ.
- Проект **смешанного формата**: основная конфигурация в EDT (`.mdo`), расширения — Designer (`Configuration.xml`); `app.format` единый → CONFIGURATION-source должен быть Designer-дампом.
- 1С connection-string через subprocess: **внутренние кавычки экранируются** (`"`→`\"`) → битый Ref → `recv returns zero`. Передавать без внутренних кавычек ИЛИ в yml (Spring парсит сам).

## Решение пользователя
Тест-ИБ — **отдельная file-ИБ**, наполнение — **config-only** (полный DumpIB-клон с данными заблокирован
неубиваемым системным фоновым заданием рабочей ИБ; рестарт службы кластера отклонён как слишком дисруптивный).
