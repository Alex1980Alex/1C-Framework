# impl-tool-observability — реализация roadmap 260713 (P0 + P1.1)

**Задача:** реализовать дорожную карту аудита логирования инструментов/MCP — корректность лога (P0) + замкнутый цикл «лог → анализ → вердикт → действие» (P1.1 / §6 decision layer).

- **Планирование:** roadmap [260713](../../docs/roadmap/260713_ROADMAP_TOOL_OBSERVABILITY_AUDIT.md) (10 ошибок B1-B10, §6 вердикты) как источник; ground-truth код прочитан (2 base-модуля, mcp-логгер, потребители, settings, паттерн post-indexing-analyzer).
- **Дизайн:** P0 — canonical-row контракт (category=tool_call зеркалит mcp_call) + фильтр потребителей вместо правки BaseHook (меньше blast-radius); P1.1 — stdlib-only аналайзер + вердикты §6.1 + Stop-detached + SessionStart-баннер (паттерны post-indexing-analyzer + acceptance_watch).
- **Кодирование:** commits [b575a2dc3](P0) + [4597efb87](P1.1). 9+8 файлов.
- **Тестирование:** 45 unit (P0: 18, P1.1: 27) + 28+11 существующих зелёные; ruff чистый; code-verify reviewer PASS ×2; detached-спавн отработал end-to-end (отчёт+verdicts+baseline).

**Отклонения от плана (обоснованы):** BaseHook не трогали для built-in; аналайзер stdlib (не duckdb); ineffective=только abandonment (repeats не движут вердикт — FP на polling); DEGRADED_MIN_CALLS=3.

**Остаётся:** P1.2 (авто MCP health_check-каденс), P1.3/P1.4, P2 (gen_ai.*-поля, rule-эффективность), P3 (OTel, LLM-judge).
