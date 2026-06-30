# Пайплайн (trivial/config): 1c-mcp-crud-mfm

Добавить инстанс `1c-mcp-crud` для базы `Srvr=DESKTOP-TNU600C;Ref=260507_DEV_ATERLETSKIY_53196`.

## 1. План
1c-mcp-crud ходит по HTTP-публикации (не Srvr/Ref) → нужна веб-публикация Apache + расширение MCP_Сервер + `.mcp.json`-инстанс.

## 2. Дизайн
Публикация `/mfm` (по текущему дампу «mfm test»; переименуемо). Шаблон — svetly (Apache `C:\Apache24`, wsap24.dll 1936). Креды — `Администратор`/(пусто) (восстановленный дамп несёт свой список пользователей; `a.terletskiy@sodru.com`→401).

## 3. Реализация
- `C:\Apache24\htdocs\mfm\default.vrd` (base=/mfm, ib=Srvr=DESKTOP-TNU600C;Ref=260507_DEV_ATERLETSKIY_53196; httpServices publishExtensionsByDefault).
- `httpd.conf`: блок `Alias "/mfm"` + `<Directory>` (SetHandler 1c-application + ManagedApplicationDescriptor).
- `.mcp.json`: инстанс `1c-mcp-crud-mfm` (URL http://localhost/mfm, SERVICE_ROOT=mcp, user=Администратор, pwd пуст, launcher mcp_1c_stdio_launcher.py).
- Рестарт службы `Apache2.4` (elevation/UAC).

## 4. Тест (верификация)
- `httpd -t` → Syntax OK; `.mcp.json` JSON OK; инстанс присутствует.
- `GET /mfm/hs/mcp/health` (Администратор/пусто, UTF-8 Basic) → **HTTP 200 `{"status":"ok"}`** (расширение MCP_Сервер на месте).
- `POST /mfm/hs/mcp/rpc` `tools/list` → **HTTP 200, 19 tools** (execute_query, execute_code, validate_query, …).
- Готча: `a.terletskiy@sodru.com`→401 (дамп = свои пользователи); httpx Basic = UTF-8 (cp1251→401). Лаунчер (httpx UTF-8) воспроизведёт.
- **Осталось пользователю:** `/mcp reconnect` → активирует `mcp__1c-mcp-crud-mfm__*`.

См. память [[reference-1c-mcp-crud-mfm-instance]].
