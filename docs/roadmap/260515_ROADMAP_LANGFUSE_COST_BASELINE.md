# 260515 — Roadmap: Langfuse Cost Baseline (§5c.7)

> **Parent:** [260509_ROADMAP_CONSOLIDATED_BACKLOG.md §5c.7](260509_ROADMAP_CONSOLIDATED_BACKLOG.md)
> **Status:** PLANNED 2026-05-15 — implementation готов к запуску. Дата start = когда накопится ≥7 дней production traffic после §5c.5 closure (2026-05-15).
> **Effort:** ~3-4 ч кодинга + ~10 мин/неделю на baseline refresh.
> **Pre-requisites done:** §5c.1-§5c.3 (Langfuse Cloud account + creds), §5c.4-§5c.5 (spans wired across hooks + framework hot-paths).
> **Research cache:** [`langfuse-cost-api-2026.md`](../../.claude/skills/tech-research/cache/langfuse-cost-api-2026.md) — concrete API patterns, schema, antipatterns.

---

## 1. Цель

Зафиксировать в `docs/architecture/cost-baselines.md` measurable baseline 5 cost-метрик production framework'а:

1. **Top-10 expensive observations** за период — где деньги уходят (cost concentration analysis).
2. **Average / P50 / P95 tokens per RAG call** — для capacity planning + alert thresholds (§5c.6).
3. **Cost breakdown by strategy** — vector / hybrid / graphrag / two_stage (через `search.manager.search` span input).
4. **Cost by model** — claude-opus vs sonnet vs haiku ratio (валидация delegation §4.5).
5. **Daily run-rate USD/day** — для финансового прогноза + threshold derivation.

## 2. Выгоды

- Закрывает acceptance criterion §7.x (cost baseline existence).
- Unblock **§5c.6** dashboard alerts — пороги для P95 latency и cost-per-query без baseline бесполезны (наугад thresholds → шум).
- Unblock **§4.5 Delegation Iter 4-5** — baseline нужен как reference для measure of improvement после router training.
- Closes ADR-010 lifecycle: `proposed` → `accepted` (см. §5c.10).
- Auto-refresh weekly даёт ranges, не точку в времени — устойчиво к outliers и model price changes.

## 3. Архитектурное решение

**Source of truth:** Langfuse Cloud (cross-instance, cross-restart, retention настроена в project settings).
**НЕ:** in-process `CostTracker` ([`analytics/cost.py`](../../src/pdf_framework/analytics/cost.py)) — теряется при restart, не агрегируется кросс-сессии. Остаётся для local feedback signal, complementary, не source-of-truth.
**Method:** Metrics API + fetch_observations с cursor pagination. **НЕ CSV-export через UI** — не масштабируется на месячные периоды (см. antipattern в cache).

**Trade-off Metrics API vs fetch_observations:**

| API | Когда | Преимущество |
|---|---|---|
| **`api.metrics.get`** | Aggregated суммы по группам (total cost, avg tokens by model) | 1 HTTP call, server-side aggregation, higher rate limit |
| **`api.observations.get_many`** | Top-N (нужны per-record для сортировки) | Гибкость локальной агрегации (например, by `obs.input.strategy` — кастомное поле span'а) |

Скрипт использует обе API в разных секциях отчёта.

**Ingestion lag 15-30s** — известный лаг Langfuse Cloud. Скрипт безопасно запускать ≥1 мин после последнего трейса; для weekly batch на закрытом окне (`to_date = yesterday`) — не проблема.

## 4. Phases

### Phase A — Skeleton & smoke (~45 мин)

> **Acceptance:** `--dry-run` отрабатывает без exceptions; на пустом периоде корректно говорит "no observations".

- [ ] **A.1** Создать [`scripts/analyze_langfuse_cost.py`](../../scripts/analyze_langfuse_cost.py) (Typer CLI):
  - Параметры: `--from-date YYYY-MM-DD`, `--to-date YYYY-MM-DD`, `--output {md|json}`, `--top-n 10`, `--tag` (optional фильтр), `--dry-run`
  - Default: `from-date = today - 7 days`, `to-date = today - 1 day` (закрытое окно, обходит ingestion lag), `output = md`
  - Шапка скрипта:
    ```python
    import typer
    from src.pdf_framework.observability.langfuse_setup import _get_langfuse_client

    app = typer.Typer()

    @app.command()
    def main(from_date: str = ..., to_date: str = ..., output: str = "md",
             top_n: int = 10, tag: str | None = None, dry_run: bool = False):
        client = _get_langfuse_client()
        if client is None:
            typer.secho("Langfuse not enabled or creds missing", fg="red")
            raise typer.Exit(1)
        ...
    ```
  - Reuses `_get_langfuse_client()` singleton из §5c.5 — НЕ создаёт новый клиент.

- [ ] **A.2** Smoke test: `python scripts/analyze_langfuse_cost.py --from-date 2026-05-15 --to-date 2026-05-15 --dry-run`
  - На пустом датасете → "no observations in range, baseline file not updated", exit 0.
  - На реальном датасете в `--dry-run` → парсит, форматирует, не пишет файл.

- [ ] **A.3** Local type-check: `.venv/Scripts/python.exe -m mypy scripts/analyze_langfuse_cost.py --ignore-missing-imports` (не блокирует на global 420 mypy errors — см. parent §5d.5).

### Phase B — Core extraction (~1.5 ч)

> **Acceptance:** 5 секций отчёта генерируются с реальными данными; error paths обработаны.

- [ ] **B.1 Section "Top-N expensive observations":**
  ```python
  from collections import defaultdict
  costs_by_name: dict[str, dict] = defaultdict(lambda: {"count": 0, "total_cost": 0.0, "total_tokens": 0})
  cursor = None
  while True:
      page = client.api.observations.get_many(
          type="GENERATION", from_start_time=from_date, to_start_time=to_date,
          limit=100, cursor=cursor, fields="core,basic,usage",
      )
      for obs in page.data:
          cost = (obs.cost_details or {}).get("total", 0.0)
          tokens = (obs.usage_details or {}).get("total", 0)
          costs_by_name[obs.name]["count"] += 1
          costs_by_name[obs.name]["total_cost"] += cost
          costs_by_name[obs.name]["total_tokens"] += tokens
      cursor = page.next_cursor
      if not cursor: break
  top_n = sorted(costs_by_name.items(), key=lambda kv: kv[1]["total_cost"], reverse=True)[:top_n]
  ```

- [ ] **B.2 Section "Average / P95 tokens per RAG call":**
  ```python
  query = {
      "view": "observations",
      "metrics": [
          {"measure": "totalTokens", "aggregation": "avg"},
          {"measure": "totalTokens", "aggregation": "p50"},
          {"measure": "totalTokens", "aggregation": "p95"},
      ],
      "filters": [{"column": "name", "operator": "contains", "value": "rag"}],
      "fromTimestamp": from_date_iso, "toTimestamp": to_date_iso,
  }
  res = client.api.metrics.get(query=query)
  ```
  Пустой результат → graceful "no RAG calls in period", не падать.

- [ ] **B.3 Section "Cost by strategy" (наши §5c.5 spans):**
  fetch_observations с `name="search.manager.search"` → локальная агрегация по `obs.input.strategy` (Langfuse не группирует по custom input fields через Metrics API).
  Output таблица: strategy × count × total_cost × avg_cost.

- [ ] **B.4 Section "Cost by model":**
  ```python
  query = {
      "view": "observations",
      "metrics": [{"measure": "totalCost", "aggregation": "sum"}],
      "dimensions": [{"field": "providedModelName"}],
      "fromTimestamp": from_date_iso, "toTimestamp": to_date_iso,
  }
  ```
  Sort by total_cost desc.

- [ ] **B.5 Section "Daily run-rate":**
  Daily Metrics API endpoint (`/api/public/metrics/daily`) — pre-aggregated daily totals.
  Output: ASCII spark-line + USD/day mean / P95 + total cost за период.

- [ ] **B.6 Error handling:**
  - **429** Too Many Requests → exponential back-off (1s → 2s → 4s → 8s → 16s, max 5 retries).
  - **401/403** → fail-fast с clear message: "Langfuse creds expired or invalid — check .env or repo secrets".
  - **Network** errors → 3 retries с jitter (±20%).
  - Декоратор `@retry` через [`tenacity`](https://tenacity.readthedocs.io/) (skill `tenacity-retry`).

### Phase C — Output formatting (~30 мин)

> **Acceptance:** `docs/architecture/cost-baselines.md` создан, читабельный, JSON mode работает для CI.

- [ ] **C.1** Markdown шаблон в `docs/architecture/cost-baselines.md` (overwrite-mode — последний run = current baseline):
  ```markdown
  # Cost Baseline (auto-generated)

  > Generated: {timestamp_iso}
  > Period: {from_date} → {to_date} ({n_days} days)
  > Source: Langfuse Cloud (cloud.langfuse.com)
  > Script: scripts/analyze_langfuse_cost.py (roadmap 260515 §5c.7)

  ## Summary
  - Total observations: {n}
  - Total cost: ${total_cost:.2f} USD
  - Run-rate: ${cost_per_day_mean:.2f} USD/day (mean) / ${cost_per_day_p95:.2f} (P95)

  ## Top-10 expensive observations
  | Rank | Name | Count | Total $ | Avg $ | Tokens |
  |---|---|---|---|---|---|

  ## Tokens per RAG call
  | Metric | Value |
  |---|---|
  | Average | ... |
  | P50 | ... |
  | P95 | ... |

  ## Cost by strategy (search.manager.search)
  | Strategy | Count | Total $ | Avg $ |
  |---|---|---|---|

  ## Cost by model
  | Model | Total $ | Share % |
  |---|---|---|

  ## Daily run-rate
  ```
  date         | $$$
  2026-05-08   | ▂
  2026-05-09   | ▃
  ...
  ```
  ```

- [ ] **C.2** JSON output mode (`--output json`) — для CI integration / dashboards. Same data, structured. Schema валидируется через Pydantic model `CostBaselineReport`.

### Phase D — Operationalization (~30 мин)

> **Acceptance:** Скрипт документирован, weekly auto-refresh настроен, §5c.7 закрыт в parent.

- [ ] **D.1** README блок:
  - Опция A: новая секция в [`09.4.1 Langfuse`](../framework%20documentation/7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.4.1_Langfuse.md#cost-baseline) — usage examples, common flags, troubleshooting (выделена в подглаву 2026-05-16).
  - Опция B: `scripts/README.md` (если уже существует) — там же отдельная подсекция.
  - Решение: Опция A — concentrated с остальной observability.

- [ ] **D.2** Weekly auto-run:
  - **Option A (recommended):** GitHub Actions cron workflow `.github/workflows/cost-baseline.yml`:
    ```yaml
    on:
      schedule:
        - cron: '0 9 * * 0'  # Sundays 9:00 UTC
      workflow_dispatch: {}
    jobs:
      baseline:
        runs-on: ubuntu-latest
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with: { python-version: '3.11' }
          - run: pip install -e ".[langfuse]"
          - env:
              OBSERVABILITY__LANGFUSE_PUBLIC_KEY: ${{ secrets.LANGFUSE_PUBLIC_KEY }}
              OBSERVABILITY__LANGFUSE_SECRET_KEY: ${{ secrets.LANGFUSE_SECRET_KEY }}
              OBSERVABILITY__LANGFUSE_ENABLED: 'true'
            run: python scripts/analyze_langfuse_cost.py
          - uses: peter-evans/create-pull-request@v6
            with:
              title: 'chore: weekly cost baseline refresh'
              body: 'Auto-generated by 260515 §5c.7'
              branch: auto/cost-baseline-refresh
    ```
    Pre-req: добавить `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` в repo secrets (one-time setup).
  - **Option B (fallback):** local pre-commit hook + manual trigger. Менее надёжно (требует Langfuse creds локально, depends on dev машина запущена).
  - **Решение между A/B:** A если репо public + GitHub Actions free quota хватает; иначе B.

- [ ] **D.3** Cross-link в parent roadmap [§5c.7](260509_ROADMAP_CONSOLIDATED_BACKLOG.md): обновить status `[ ] DEFERRED` → `[x] DONE` после первого успешного auto-run.

### Phase E — Validation (~15 мин)

> **Acceptance:** Baseline данные совпадают с Langfuse UI (±1%); sanity-check проходит.

- [ ] **E.1** Sanity check: total_cost из Metrics API ≈ `Σ(obs.cost_details.total)` из observations API за тот же период. Расхождение >5% — баг (вероятно ingestion race или filter mismatch).
- [ ] **E.2** Sample manual: открыть Langfuse UI → выбрать 1 expensive query → сравнить cost в UI vs строка в нашем отчёте. Should match exactly (oba используют один и тот же `cost_details.total`).
- [ ] **E.3** Решение: `docs/architecture/cost-baselines.md` **коммитится** (не gitignored). Преимущества: history через `git log -p cost-baselines.md` показывает cost drift over time. Не PII (агрегаты), не secret.

## 5. Acceptance criteria

- [ ] [`scripts/analyze_langfuse_cost.py`](../../scripts/analyze_langfuse_cost.py) существует, проходит `--dry-run` без exceptions
- [ ] [`docs/architecture/cost-baselines.md`](../architecture/cost-baselines.md) существует с реальными данными за first 7-day window
- [ ] Total cost в отчёте совпадает (±1%) с Langfuse UI dashboard для того же period
- [ ] Weekly auto-refresh настроен (Option A или B)
- [ ] [§5c.6](260509_ROADMAP_CONSOLIDATED_BACKLOG.md) dashboard thresholds derived from baseline (становится возможным после close §5c.7)
- [ ] [§5c.10](260509_ROADMAP_CONSOLIDATED_BACKLOG.md) ADR-010 status переведён `proposed` → `accepted`

## 6. Risks & gotchas

| Риск | Митигация |
|---|---|
| Custom models (Qwen3 local, embeddings) → `cost_details.total = null` | Добавить model pricing в Langfuse Project Settings → Models ДО первого run (one-time). Если нет — graceful skip с warning в отчёте + список null-cost models. |
| > 100K observations за неделю → fetch_observations pagination slow | Switch to [Blob Storage Export](https://langfuse.com/docs/api-and-data-platform/features/export-to-blob-storage) (S3/GCS scheduled). Не нужен initially для текущего volume. |
| `flush=False` traces ещё в очереди при run | Для weekly batch на `to_date = yesterday` — не проблема (>24h gap). Для on-demand run — `client.flush()` перед запросом. |
| Ingestion lag 15-30s | `to_date = today - 1 day` (closed window) обходит полностью. |
| Daily Metrics API vs live Metrics API расхождение | Daily — pre-aggregated rollup (может устареть после re-ingestion); live — current state. Использовать **только live** для baseline; Daily — только для spark-line визуализации. |
| Creds expired/rotated → 401 | Скрипт fails fast с clear message. Runbook: где обновить creds в `.env` + repo secrets (см. parent §5c.2 + 09.4 Мониторинг). |
| Custom model price change retroactively | Langfuse cost_details — frozen at ingestion. Старые traces сохраняют старую цену. Baseline отражает реальные траты, не текущие цены. |

## 7. Когда НЕ делать

- Если framework только для **local dev / research** без production users — baseline бесполезен (нет cost). Достаточно in-process `CostTracker`.
- До §5c.5 closure (DONE 2026-05-15) — нет spans → нет данных в Langfuse.
- До накопления **≥7 дней** реальных запросов — baseline на 1-2 днях шумный, не репрезентативен.
- Если Langfuse self-hosted без persistent storage — данные исчезают при restart, baseline не имеет смысла.

## 8. После закрытия §5c.7

Открываются:

- **§5c.6** Dashboard alerts — thresholds можно derive из baseline (P95 latency × 1.5 как warning, × 2 как red-line; cost-per-query × 2 как alert).
- **§5c.10** ADR-010 переходит `proposed` → `accepted` (есть production data + cost reality check).
- **§4.5 Iter 4** Delegation router training — baseline = reference point для measuring improvement after training.
- **§5c.9** Outcome corpus (требует 30 дней) — 7-day mini-corpus от §5c.7 = stepping stone, можно начинать prototype схемы JSONL.

## 9. Источники

- **Tech cache:** [`langfuse-cost-api-2026.md`](../../.claude/skills/tech-research/cache/langfuse-cost-api-2026.md) — concrete API patterns, response schemas, antipatterns (extraction side)
- **Arch cache:** [`langfuse-standalone-spans-2026.md`](../../.claude/skills/architecture-research/cache/langfuse-standalone-spans-2026.md) — emit_observation pattern (ingestion side; sibling cache)
- **Existing local infra:** [`src/pdf_framework/analytics/cost.py`](../../src/pdf_framework/analytics/cost.py) — in-process estimator (complementary, not replaced)
- **Parent roadmap:** [`260509_ROADMAP_CONSOLIDATED_BACKLOG.md §5c.7`](260509_ROADMAP_CONSOLIDATED_BACKLOG.md)
- **Langfuse official:**
  - [Token & Cost Tracking](https://langfuse.com/docs/observability/features/token-and-cost-tracking) — schema reference
  - [Query via SDKs](https://langfuse.com/docs/api-and-data-platform/features/query-via-sdk) — Python SDK examples
  - [Observations API](https://langfuse.com/docs/api-and-data-platform/features/observations-api) — pagination, fields
  - [Daily Metrics API FAQ](https://langfuse.com/faq/all/costs-tokens-langfuse) — daily totals
- **Related skills:** `tenacity-retry` (retry pattern для B.6), `claude-code-github-actions` (Phase D.2 workflow setup)
