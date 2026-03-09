# Чеклист готовности: Фаза 64 — Code Intelligence MCP

**Приоритет:** MEDIUM | **Срок:** 3-4 дня | **Зависимости:** Фазы 59, 61, 62

## Предусловия
- [ ] Фаза 59 (Symbol Search) завершена и API доступно
- [ ] Фаза 61 (Call Graph) завершена, данные актуальны
- [ ] Фаза 62 (Object Metadata) завершена, API для метаданных работает
- [ ] Утверждена архитектура Smart Routing (маршрутизация запросов между модулями)
- [ ] Подготовлена MCP спецификация для 6 инструментов

## Артефакты (файлы/код)
- [ ] `src/bsl/mcp_server/code_intelligence.py` — точка входа MCP сервера
- [ ] `src/bsl/mcp_server/tools/find_symbol.py` — поиск символа (делегирует к Фазе 59)
- [ ] `src/bsl/mcp_server/tools/call_graph.py` — `get_callers`, `get_impact` (делегирует к Фазе 61)
- [ ] `src/bsl/mcp_server/tools/object_info.py` — `get_object_info` (делегирует к Фазе 62)
- [ ] `src/bsl/mcp_server/tools/analyzer.py` — `find_dead_code` (анализ графа)
- [ ] `.mcp/bsl.json` обновлён: сервер `bsl-code-intelligence` зарегистрирован

## Метрики приёмки
- [ ] Все 6 tools доступны и работают: find_symbol, get_callers, get_impact, find_dead_code, get_object_info, contextual_search
- [ ] Latency find_symbol: < 200ms (p95)
- [ ] Latency get_impact: < 1.5s для стандартного модуля
- [ ] Precision find_dead_code: >= 90%
- [ ] Тестовое покрытие routing модуля: >= 80%

## Интеграционные проверки
- [ ] find_symbol: поиск процедуры возвращает файл и строку
- [ ] get_callers: полный список мест использования символа
- [ ] get_impact: изменение метода → список зависимых модулей
- [ ] get_object_info: структура, реквизиты и метаданные объекта 1С
- [ ] find_dead_code: детектирует неиспользуемый тестовый метод
- [ ] Graceful Degradation: при недоступности backend → понятная ошибка, не crash

## Блокеры для следующих фаз
- [ ] Без единого MCP блокируется Фаза 66 (Coding Assistant: унифицированный доступ к анализу)
- [ ] Без get_impact блокируется безопасный рефакторинг
