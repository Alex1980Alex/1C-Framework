# Пайплайн: Подключение ERP-базы к MCP (1c-mcp-crud)

> **Инфраструктура:** публикация 1С-базы на Apache + расширение `MCP_Сервер` + инстанс прокси в `.mcp.json`. Триггер — пользователь добавил расширение `MCP_Сервер` в ERP-базу (скриншот конфигуратора). Компактный артефакт по ADR-018.

## 1. Планирование
Дано: в `Enterprise20_2_5_27_52` добавлено и активно расширение `MCP_Сервер`. Цель — сделать базу доступной через `1c-mcp-crud`, как `transport`.
Разведка: веб-сервер = **Apache 2.4** (`C:\Apache24`), не IIS; `transport` опубликован `/transport` + `default.vrd` с `<httpServices publishExtensionsByDefault=true>`; `.mcp.json` имел один инстанс (transport). Пользователь выбрал «подключить полностью».

## 2. Дизайн  (одобрено)
- Публикация `/erp` через `webinst` (Apache), с бэкапом `httpd.conf`.
- `default.vrd` дополнить `<httpServices publishByDefault publishExtensionsByDefault/>` (MCP-сервис — в расширении).
- Инстанс `1c-mcp-crud-erp` в `.mcp.json` (URL `/erp`, креды демо-базы).

## 3. Исполнение
1. `webinst -publish -apache24 -wsdir erp …` → `Enterprise20_2_5_27_52` (exit 0); `httpd.conf` += `Alias "/erp"` + Directory.
2. `default.vrd`: добавлен `<httpServices publishByDefault="true" publishExtensionsByDefault="true"/>` (webinst его не положил → иначе 404).
3. Apache restart с **UAC** (Start-Process -Verb RunAs, служба Running).
4. `.mcp.json` += `1c-mcp-crud-erp` (JSON валиден).

## 4. Верификация
- `GET /erp/hs/mcp/health`: **401** без auth, **200** `{"status":"ok"}` с `Admin`/пустой пароль.
- `POST /erp/hs/mcp/rpc tools/list`: **200, 19 инструментов** (полная сборка расширения, не урезанная на 2).
- Креды демо-базы: `Admin` / пустой пароль.
- **Действие пользователя:** `/mcp reconnect` → активируются `mcp__1c-mcp-crud-erp__*`, далее финальная проверка реальным `execute_query`.

Память: `reference_dev_infobases.md` — раздел «Публикация базы для MCP (1c-mcp-crud, Apache)».
