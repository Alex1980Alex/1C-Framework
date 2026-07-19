# fix-yaxunit-runner-recovery (trivial, 2026-07-19)

Восстановление YAxUnit-контура этапа 4: mcp-onec-test-runner на TM_UnitTest.

- Корень 1: предзагруженные YAXUNIT/UnitTests ломали create-предусловие раннера («уже существует»)
- Корень 2: полная DESIGNER-сборка > 120с MCP-таймаута (первый прогон падает, повторный — инкремент)
- Корень 3: LoadConfigFromFiles пересоздаёт расширения с SafeMode=ON → снято через V83.COMConnector (32-bit PS)
- Результат: ЮТТПримерТест 2/2 PASSED (13.0с), junit-отчёт
- Кода фреймворка не менялось; артефакты — память reference-yaxunit-runner-recovery-recipe + этот pipeline.md
