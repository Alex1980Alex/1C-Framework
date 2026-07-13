# 02 Дизайн — P2.3 (спека = roadmap 260713 §5 P2.3)

## Решения
1. **Единый shared helper** `scripts/mcp_call_log.py` — stdlib-only (без зависимости от src.memory),
   импортируется из обоих path-изолированных процессов. `log_mcp_call()` + контекст `track_call()`
   (таймер + auto-логирование ok/error_type на выходе, ре-райз исключения).
2. **memory-orchestrator** (наш код): защитный импорт `scripts.mcp_call_log` + no-op fallback;
   `call_tool` → тонкая обёртка `track_call`, тело вынесено в `_dispatch_tool`; ветки ошибок
   явно помечают `state` (без эвристик по тексту результата).
3. **1c-mcp-crud** (вендоренный сабмодуль): НЕ трогаем `external/1c_mcp/`. Обёртка = монки-патч
   `OneCClient.call_tool` в лаунчере (наш код), идемпотентный флаг `_mcp_call_logged`.
   `isError` результата → ok=False/`tool_error`.

## Ключевой риск (пойман при реализации)
`sys.path.append(project_root)` тащит регулярный пакет `<root>/src/` в скан → шедоуит
namespace-пакет `external/1c_mcp/src/` → ломает `from src.py_server.main import main`.
**Фикс:** на path кладётся каталог `scripts/` + bare `import mcp_call_log` (корневой `src` в скан не попадает).
