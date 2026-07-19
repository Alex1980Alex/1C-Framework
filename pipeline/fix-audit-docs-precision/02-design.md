# Design — Починка точности audit_docs_skills.py

## Проблема (по итогам анализа)
Аудит выдал 141 «gap», из них ~139 ложных. Баннер `[AUDIT-COVERAGE]` кричит волком.
4 корневых бага точности в [`scripts/audit_docs_skills.py`](../../scripts/audit_docs_skills.py).

## Правки

### 1. Префикс endpoint'ов (`_extract_router_prefix`, L105-118)
Экстрактор читает `prefix=` только из `include_router()` в app.py. Но роутеры объявляют
префикс на конструкторе: `openai_compat.py` → `APIRouter(prefix="/v1")`, `websocket.py` → `APIRouter()` (root).
**Фикс:** сначала искать `APIRouter(...prefix=...)` в тексте модуля; если `APIRouter(` есть, но префикса нет → `""` (root-mount) ПОСЛЕ проверки app.py; иначе fallback `/{stem}`.
Ожидание: `/v1/chat/completions`, `/v1/embeddings`, `/v1/models`, `/ws/search`. → -4 FP.

### 2. Мангление имён стратегий (`_class_to_strategy_name` L200-205 + `_feature_documented` strategy L563-569)
`re.sub(r"(?<!^)(?=[A-Z])","_")` рвёт акронимы: `GraphRAGAuto`→`graph_r_a_g_auto`. Канон в коде — `graphrag_*`/`lightrag`.
**Фикс мангла:** акроним-aware — граница `[a-z0-9]→[A-Z]` и `[A-Z]→[A-Z][a-z]` → `graph_rag_auto`, `light_rag`, `web`.
**Фикс матчинга:** стратегия задокументирована, если `name`/no-underscore/hyphen в тексте ЛИБО все токены `split("_")` присутствуют (04.3 содержит «graphrag»+«lightrag»+«Auto»). → -4 FP (web может остаться — реальный минорный gap).

### 3. Узкий allowlist доков (`run_audit` L618-641)
Фича сверяется только с 2-4 захардкоженными файлами; главы 44.3/50.x невидимы.
**Фикс:** whole-tree fallback — фича = doc_gap только если НЕ в target И НЕ нигде в дереве `docs/`.
`_all_docs_text()` (walk+cache). Target остаётся «предпочтительным местом» в action-item. → -9 hook FP, -27 memory FP, -9 bsl FP.

### 4. Класс-как-фича (`extract_memory_subsystems` L437, `extract_bsl_tools` L465)
Каждый не-`_` класс = «пользовательская фича». Датаклассы/реестры/кэши — внутренности.
**Фикс:** фильтр по `__all__` пакета (`<sub>/__init__.py`) — публичный API. Нет `__all__` → классы не включаем.
Комбинация с #3: остаются только экспортированные-и-нигде-не-упомянутые (законный минорный сигнал).

## Инварианты (не сломать)
- 84/88 endpoint, 100% cli/config/mcp/agent покрытие — не регрессировать (после прогона total не растёт, зелёные не краснеют).
- `--update` updaters не трогаю (правлю только детект/матчинг).
- Поведение при отсутствии файлов — graceful (как сейчас).

## Проверка
- Новый `tests/unit/test_audit_docs_precision.py`: prefix v1/ws, мангл graphrag_auto/light_rag, токен-матч, whole-tree fallback, `__all__` фильтр.
- Прогон `--json`: 141 gap → ожидаемо ≤ ~15 (только законные).
- code-verify (inline + субагент-ревьюер, read-only).
