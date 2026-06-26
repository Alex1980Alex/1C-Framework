# Тестирование (верификация)

ВЫПОЛНЕНО: деплой UnitTests в ИБTransportManagementDevelop PASS (LoadConfigFromFiles 0 / UpdateDBCfg 0 — платформа скомпилировала+приняла); code-verify PASS (S1 ревьюер + S2/S3 implementer-агенты); skill-router-config.json валиден (json.load).
ОТЛОЖЕНО (env-блок, решение пользователя B): живой YAxUnit green-run — раннер прибит к недоступному KOMPUTER\TestDB; локальный conn для прогона = Srvr=\"DESKTOP-TNU600C\";Ref=\"ИБTransportManagementDevelop\" (правка .env ONEC_TEST_CONN + /mcp reconnect → /run-1c-unit-tests ЮТТПримерТест). Документировано в 17.6 + командах.
