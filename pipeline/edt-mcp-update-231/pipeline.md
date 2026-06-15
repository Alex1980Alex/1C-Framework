# Пайплайн (trivial): Обновление плагина EDT-MCP 1.26.1 → 2.3.1

Операционная задача: обновить Eclipse/EDT-плагин `com.ditrix.edt.mcp.server` (DitriXNew/EDT-MCP)
до релиза v2.3.1. В репозитории кода не правилось — `.mcp.json` версионно-независим
(прокси `mcp-remote` → `localhost:8765`). Артефакты процесса (память) — вне репо.

## 1. План
- Найти, где реально живёт EDT-MCP: `.mcp.json` → `mcp-remote localhost:8765`; плагин стоит p2-бандлом
  в 1C:EDT (Lite) 2025.2 (`bundles.info` → `…/.p2/pool/plugins/com.ditrix.edt.mcp.server_1.26.1.jar`);
  в 2026.1 плагина нет.
- Релиз v2.3.1 = p2 update-site (`MCP-EDT.v2.3.1.zip`); OSGi-версия бандла переномерована в 2.3.1.
- Подтверждено пользователем (AskUserQuestion): «Закрыть EDT и обновить сейчас».

## 2. Дизайн
- Метод: официальный headless **p2 director** (README), pin на локальный распакованный update-site
  (детерминизм), а не онлайн GitHub Pages.
- Безопасность/обратимость: бэкап `bundles.info`, старый jar остаётся неактивным в пуле, артефакты
  в `C:\Temp\edt-mcp-2.3.1\`.

## 3. Реализация
1. `gh release download v2.3.1` → проверка sha256 (`b836d6c…0801`) → `Expand-Archive` в ASCII-путь.
2. Бэкап `bundles.info`; закрытие EDT 2025.2 (1cedt + 1cedtstart + leftover javaw:8765).
3. p2 director (call-operator PowerShell): `1cedtc.exe -vm <axiom-jdk java.exe> -nosplash -consoleLog
   -application …director -repository file:/…/site/ -uninstallIU …group/1.26.1 -installIU …group/2.3.1
   -destination <install> -bundlepool <pool> -shared <.p2> -profileProperties …reconcile=true` → exit 0.
4. Перезапуск через `1cedtstart.exe`.

Три ключевых грабли (4 неудачных попытки): обязательный `-vm` (иначе лаунчер exit 1 без лога),
shared-параметры (`-destination/-bundlepool/-shared`), атомарный uninstall+install (иначе exit 13
«conflicting requirements» из-за singleton feature.jar).

## 4. Тест / верификация
- `bundles.info` → `com.ditrix.edt.mcp.server_2.3.1.jar` ✅
- Сервер 8765 поднялся (новый javaw), `mcp__edt-mcp__get_edt_version` → `2025.2.6.4` ✅
- После `/mcp reconnect` появился новый toolset v2.3.1 (`create_project`, `create_infobase`,
  `create_launch_config`, `modify_metadata`, `get_server_status`, toolset-management) ✅

Рецепт сохранён в память: `reference_edt_mcp_plugin_update.md`.
