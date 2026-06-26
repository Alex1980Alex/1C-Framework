# 02 Дизайн — Wire mcp-onec-test-runner

## Компоненты
1. **Тест-ИБ** `C:\onec-test-bases\TM_UnitTest` (file, изолирована от кластера/рабочей ИБ):
   - `CREATEINFOBASE File=...` (без внутренних кавычек — subprocess их экранирует).
   - `DESIGNER /LoadConfigFromFiles <Designer-дамп> -Format Hierarchical` + `/UpdateDBCfg`.
   - Designer-дамп конфигурации получен `DESIGNER /DumpConfigToFiles` рабочей ИБ (8727 файлов).
   - ИБ без пользователей → connection без user/password.

2. **Конфиг раннера** — генерится launcher'ом в gitignored `tools/mcp-jars/.runtime/application.yml`:
   - `format: DESIGNER`, `base-path: <репо>` (покрывает и конфиг, и расширения).
   - source-set: **CONFIGURATION** `tools/mcp-jars/.runtime/config-src` (Designer-дамп, gitignored) +
     EXTENSION `src/bsl/exts/YAXUNIT` [MAIN,YAXUNIT] + EXTENSION `src/bsl/exts/UnitTests` [TESTS,YAXUNIT].
   - `connection.connection-string` из `.env ONEC_TEST_CONN`, user/password из `.env` (пусто для config-only).
   - `tools.builder: DESIGNER`, `enterprise.additional-launch-keys: [/TESTMANAGER]`.

3. **Launcher** `scripts/onec_test_runner_launch.py` — переписан: вместо мёртвых CLI-флагов генерит yml из
   `.env` и запускает jar с `--spring.config.additional-location=file:.runtime/` (профиль `mcp` дефолтный).

## Безопасность
- `.gitignore += tools/mcp-jars/.runtime/` + `application-*.yml` (креды/дамп не в git).
- Untrack пред-существующего `application-testdb.yml` (был закоммичен с открытым паролем — отдельная ремедиация: ротация + чистка истории).

## Альтернативы (отклонены)
- Серверная копия ИБ — thick-client раннер работает, но создание копии требует cluster-admin/SQL-кредов (нет).
- Полный DumpIB-клон — заблокирован неубиваемым системным фоновым заданием (эксклюзив недостижим без рестарта службы).

## Одобрение
Дизайн одобрен (config-only выбран пользователем; минимальные изменения; изоляция тест-ИБ соблюдена).
