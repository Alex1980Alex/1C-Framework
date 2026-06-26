# 01 Планирование — Fix mcp-onec-test-runner conn + _dotenv

## Проблема
MCP-сервер `mcp-onec-test-runner` падал на старте (`✘ failed`).

## Корень (диагностика)
1. `.env:74` указывал на несуществующий `Srvr="KOMPUTER";Ref="TestDB"` (реальный хост — `DESKTOP-TNU600C`, ИБ `ИБTransportManagementDevelop`).
2. Баг `scripts/_dotenv.py:26`: `val.strip('"')` срезал закрывающую кавычку у любой строки, кончающейся на `"` → connection-строка приходила битой (`...Ref="TestDB` без закрывающей `"`).

> Примечание: третий, более глубокий блокер (launcher шлёт CLI-флаги, которых jar v0.5.1 не знает; нужен Spring-профиль `app.*`) — вне scope этого пайплайна, ведётся отдельно по решению пользователя (тест-ИБ).

## Scope
Только корни №1 и №2 (config + parser). Без изменения контракта launcher.
