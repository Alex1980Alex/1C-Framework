# 02 — Дизайн

Все правки — минимальные, локальные, того же класса, что P0/P1 (coerce на границе,
honest-failure, tz-нормализация). Один принцип на пункт:

- **Item 1** `get_categories`: `avg = row[2]; "avg_importance": round(avg, 2) if avg is not None else None`.
  None = «нет числовой важности» честнее, чем 0.0 (0.0 = ложное «важность ноль»).
- **Item 2** `delete_message`: обернуть post-commit side-effects (`_cleanup_links` + `_record_ingest`)
  в широкий try с логом — delete уже закоммичен, его успех не должен зависеть от cleanup/observability.
  `links_removed` остаётся best-effort (0 при фейле). Ответ по-прежнему `success=deleted>0`.
- **Item 3** `dashboard.compute_docs_freshness`: нормализовать ОБА операнда к naive-local:
  `x.astimezone().replace(tzinfo=None) if x.tzinfo else x`. Симметрично, корректно при любой
  комбинации aware/naive (паттерн M9 `_naive`).
- **Item 5** `memcube`: `normalize_pattern_type(self.metadata.get("pattern_type"))[0]` на обеих
  границах (canonical default `workflow-pattern` из коэрсера, единый). Provenance не нужен
  (конвертер, не писатель в store).
- **Item 6** `from_string` (×3): `raise ValueError(f"Unknown {kind}: {value!r}. Valid: {[m.value for m in cls]}")`.
  Остаётся ValueError → `except ValueError` у вызывающих (dedupe `apply_link_plan`) не ломается.
- **Item 4** RRF: код НЕ меняем (см. 01 замер+обоснование). Добавляем поясняющий комментарий
  у `rrf_scores[item.unified_id]` — «кросс-store дубли = зеркала, коллапсит Deduplicator; НЕ
  суммируем ранги намеренно (redundancy ≠ corroboration), см. роадмап 260716 §3.3».

## Одобрение

Пред-решено анализом + замером RRF. Правки поведение-сохраняющие, кроме устранения crash-путей.
Одобряю.
