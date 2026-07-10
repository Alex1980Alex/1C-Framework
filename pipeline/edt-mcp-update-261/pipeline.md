# EDT-MCP plugin update 2.5.1 → 2.6.1 (trivial, операционная задача)

## Задача
Обновить Eclipse-плагин `com.ditrix.edt.mcp.server` в 1C:EDT (Lite) 2025.2 с 2.5.1 до 2.6.1 (запрос пользователя «обнови в EDT» + changelog v2.5.1...v2.6.1).

## Выполнено (headless p2 director, рецепт reference-edt-mcp-plugin-update)
1. Диагностика падения `edt-mcp` (-32000) = транзиентная гонка старта EDT; после прогрева порт 8765 ожил.
2. Скачал `MCP-EDT.v2.6.1.zip`, sha256 совпал с релизом (`26141341…60ae0c25`).
3. Распаковал update-site, забэкапил `bundles.info`, закрыл EDT.
4. p2 director: атомарно `-uninstallIU …/2.5.1 -installIU …/2.6.1` → exit 0, «Operation completed».
5. `bundles.info` → 2.6.1; перезапуск EDT (`-vm` Axiom); порт 8765 up за ~50с.
6. Верификация: `tools/list` = 76 тулов, новые 2.6.1 (`get_outgoing_structures`, `export_common_picture`, `list_common_pictures`) присутствуют.
7. Обновлён memory-трекер `reference-edt-mcp-plugin-update`.

## Осталось за пользователем
`/mcp reconnect` — сессия держит кэш tools/list от 2.5.1.

## Изменения кода
Нет product-кода. Единственная правка — memory-файл `.claude/…/memory/reference_edt_mcp_plugin_update.md` (трекер версий).
