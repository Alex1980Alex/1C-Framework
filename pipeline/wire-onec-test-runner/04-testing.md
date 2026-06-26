# 04 Тестирование — Wire mcp-onec-test-runner

## ✅ Что верифицировано (исходный баг устранён)
MCP-probe против launcher (live):
- **Раннер СТАРТУЕТ**: `INIT_OK=True`, `TOOLS_OK=True`, tools = `run_all_tests`, `run_module_tests`, `dump_config`.
  (Прежде: `APPLICATION FAILED TO START / basePath null / Требуется source set CONFIGURATION` → `✘ failed`.)
- **Конфиг принят**: `Проверка конфигурации завершена: isValid=true, ошибок=0, предупреждений=0`.
- **Build-pipeline отработал**: раннер собрал конфиг+расширения и запустил исполнение тестов:
  `1cv8c.exe ENTERPRISE /IBConnectionString "File='C:\onec-test-bases\TM_UnitTest';" /TESTMANAGER /C RunUnitTests=<json>`.
- **`run_all_tests` вернул ответ** по MCP (end-to-end канал жив).

→ Исходный симптом `mcp-onec-test-runner · ✘ failed` **вылечен**: после `/mcp reconnect` сервер поднимется и ответит.

## ⚠ Открытый пункт (отдельная проблема — исполнение)
Тонкий клиент `1cv8c.exe /TESTMANAGER` отработал старт (~16с CPU) и **сел в простой** (onec_log 0 байт,
процесс жив 5+ мин) — YAxUnit-автозапуск через `RunUnitTests` не завершил работу системы, клиент остался
в главном интерфейсе. Раннер ждал отчёт → после ручного снятия клиента вернул «Не удалось проанализировать отчёт».

**Гипотезы** (для follow-up): (1) тонкому клиенту `1cv8c.exe` нужна клиентская лицензия (диалог); (2) session-start
handler YAXUNIT-расширения не отрабатывает `RunUnitTests` в config-only ИБ; (3) стартовый диалог тонкого клиента
блокирует headless-прогон. Не баг раннера/конфига — слой исполнения тестов.

## code-verify
launcher: reviewer FAIL (`.runtime/` не в gitignore) → исправлено (gitignore + untrack `application-testdb.yml`);
yq(platform_version) применён. Функциональные пункты PASS. Повторный live-probe = раннер стартует.

## Критерий «готово» (этого трека)
Раннер стартует, принимает app.*-конфиг, валидирует и запускает прогон — **достигнуто**. Полный зелёный Smoke
(JUnit PASS) упирается в headless-исполнение тонкого клиента — вынесено в follow-up.
