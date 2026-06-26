# 03 Кодирование — Wire mcp-onec-test-runner

## Изменённые/созданные артефакты
- `scripts/onec_test_runner_launch.py` — **переписан**: генерит `application.yml` из `.env` (app.* со
  source-set CONFIGURATION+2 EXTENSION), запускает jar с `--spring.config.additional-location`. yq()
  экранирует YAML double-quoted скаляры.
- `.env` — `ONEC_TEST_CONN=File='C:\onec-test-bases\TM_UnitTest';`, `ONEC_DB_USER`/`ONEC_DB_PWD` пусто
  (config-only ИБ без пользователей).
- `.gitignore` — `tools/mcp-jars/.runtime/` + `tools/mcp-jars/application-*.yml`.
- `git rm --cached tools/mcp-jars/application-testdb.yml` (untrack утёкшего конфига).
- Тест-ИБ `C:\onec-test-bases\TM_UnitTest` — наполнена (CREATEINFOBASE rc=0 → LoadConfigFromFiles rc=0/42s → UpdateDBCfg rc=0/10s).
- Designer-дамп конфигурации → `tools/mcp-jars/.runtime/config-src` (8727 файлов, gitignored).

## Инфраструктурные находки (ключевые)
- Кластер 1936 жив; thick-client DESIGNER к нему работает — прежний `recv returns zero` был артефактом
  экранирования кавычек subprocess'ом (Ref ломался). Передавать connection без внутренних кавычек.
- DumpIB требует эксклюзив; рабочая ИБ держит неубиваемое системное фоновое задание (session-id 2,
  app-id BackgroundJob) — `terminate` его не берёт, scheduled-jobs-deny не убирает.

## code-verify
launcher: reviewer PARTIAL → FAIL по `.runtime/` не в gitignore → **исправлено** (gitignore + untrack);
минор yq(platform_version) применён. Остальные пункты PASS (схема app.* совпала с эталоном, ruff чист).
