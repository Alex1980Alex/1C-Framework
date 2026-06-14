---
name: duckdb-analytics
description: "DuckDB SQL-аналитика над JSONL/Parquet логами без миграции (read_json_auto). ИСПОЛЬЗУЙ когда нужно посчитать метрики/агрегаты над *.jsonl логом (hook-invocations, memory-ingestion, skill-accuracy), p50/p95 латентность, перцентили, экспорт в Parquet. Триггеры: 'duckdb', 'read_json_auto', 'SQL по jsonl', 'аналитика по логам', 'union_by_name', 'approx_quantile', 'query jsonl', 'in-memory SQL', 'COPY TO parquet'. НЕ для векторного поиска (→ qdrant-operations), НЕ для observability-отчётов как готового продукта (→ memory-unified)."
---

# DuckDB Analytics — SQL без миграции над JSONL/Parquet логами

## Обзор

DuckDB читает JSONL-логи напрямую через `read_json_auto` — никакой загрузки в БД, схема выводится автоматически. In-process (как SQLite), in-memory (`:memory:`), на порядки быстрее `grep`/`jq`-сканов на больших логах. В этом фреймворке так устроены `audit_query.py` (hook-invocations), `memory_observability_query.py` (8 sinks), `skill_ingest_trend.py` (ingestion-тренды), `archive_jsonl_to_parquet.py` (cold tier). Этот скилл — канон их паттернов + подводные камни schema-inference.

**Источники знаний:** официальные доки DuckDB (`duckdb.org/docs/stable/data/json/loading_json`), GitHub issue [duckdb/duckdb#14259](https://github.com/duckdb/duckdb/issues/14259) (schema-inference баг), внутренние скрипты `scripts/audit_query.py` + `scripts/archive_jsonl_to_parquet.py`.

---

## Быстрый справочник

| Задача | Конструкция |
|--------|-------------|
| Читать JSONL | `read_json_auto('f.jsonl', format='newline_delimited', union_by_name=true)` |
| In-memory коннект | `duckdb.connect(":memory:")` |
| Дрейф схемы между строками/файлами | `union_by_name=true` |
| Перцентили | `approx_quantile(col, 0.95)` |
| Группировка по дню | `date_trunc('day', CAST(ts AS TIMESTAMP))` |
| Параметры (без инъекции) | `con.execute(sql, [val])` + `?` плейсхолдеры |
| View над логом | `CREATE OR REPLACE VIEW logs AS SELECT * FROM read_json_auto(...)` |
| Экспорт в Parquet | `COPY (SELECT * FROM logs) TO 'x.parquet' (FORMAT PARQUET, COMPRESSION ZSTD)` |
| Читать Parquet cold tier | `read_parquet(['a.parquet','b.parquet'], union_by_name=true)` |
| Объединить JSONL + Parquet | `(...) UNION ALL BY NAME (...)` |

---

## Установка

```bash
pip install duckdb        # или: uv pip install duckdb
```

Всегда guard'ить импорт (графдеградация, а не краш):

```python
def _check_duckdb() -> bool:
    try:
        import duckdb  # noqa
        return True
    except ImportError:
        print("ERROR: duckdb not installed. Run: pip install duckdb", file=sys.stderr)
        return False
```

---

## Основной API (официальные доки)

| Параметр | Назначение | Дефолт |
|----------|------------|--------|
| `format` | `auto` / `newline_delimited` (JSONL) / `array` / `unstructured` | `auto` |
| `auto_detect` | вывод схемы | `true` |
| `union_by_name` | унифицировать схему между файлами/строками | `false` |
| `ignore_errors` | пропускать битые строки (**только** newline_delimited) | `false` |
| `columns` | явная схема `{name:'TYPE'}` — обходит баги inference | — |
| `sample_size` | строк для inference; `-1` = весь файл | `20480` |
| `maximum_object_size` | макс. размер JSON-объекта, байт | `16777216` |
| `records` | `auto`/`true`/`false` (STRUCT-колонка) | `auto` |

`read_ndjson(f)` ≡ `read_json(f, format='newline_delimited')`. Можно `SELECT * FROM 'file.jsonl'` напрямую. Отсутствующие ключи → `NULL`.

---

## Паттерн 1: pre-clean + view над «грязным» JSONL (канон фреймворка)

**Зачем pre-clean, а не `ignore_errors=true`:** при битых строках `ignore_errors=true` СХЛОПЫВАЕТ схему в одну колонку `json` (проверено в `audit_query.py`). Поэтому фильтруем мусор в Python, а DuckDB читает уже чистый temp-файл с полноценным inference.

```python
import atexit, json, os, tempfile
from pathlib import Path

def build_logs_view(con, log_path: Path) -> str:
    """Pre-clean JSONL → temp-файл → CREATE VIEW logs. Возвращает путь temp для уборки."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8", newline="\n"
    )
    bad = 0
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if not s:
                    continue
                try:
                    json.loads(s)
                except (ValueError, json.JSONDecodeError):
                    bad += 1
                    continue
                tmp.write(s + "\n")
    finally:
        tmp.close()
    atexit.register(lambda p=tmp.name: os.path.exists(p) and os.unlink(p))
    if bad:
        print(f"(skipped {bad} malformed lines)", file=sys.stderr)
    # union_by_name=true — дрейф схемы между типами событий безвреден.
    # БЕЗ ignore_errors — temp уже чистый (обходит issue #14259).
    con.execute(
        f"CREATE OR REPLACE VIEW logs AS SELECT * FROM read_json_auto("
        f"'{tmp.name}', format='newline_delimited', union_by_name=true)"
    )
    return tmp.name
```

---

## Паттерн 2: предопределённые view + параметры + TSV-вывод

```python
import duckdb, sys

VIEWS = {
    "latency-p95": """
        SELECT hook, COUNT(*) AS calls,
               approx_quantile(elapsed_ms, 0.5)  AS p50_ms,
               approx_quantile(elapsed_ms, 0.95) AS p95_ms,
               approx_quantile(elapsed_ms, 0.99) AS p99_ms
        FROM logs WHERE elapsed_ms > 0
        GROUP BY hook ORDER BY p95_ms DESC LIMIT 30
    """,
    "per-day": """
        SELECT date_trunc('day', CAST(ts AS TIMESTAMP)) AS day,
               store, COUNT(*) AS events
        FROM logs WHERE store = ?          -- параметр, не f-string
        GROUP BY day, store ORDER BY day DESC
    """,
}

con = duckdb.connect(":memory:")
tmp = build_logs_view(con, log_path)
try:
    res = con.execute(VIEWS["per-day"], ["skill_library"])   # значения → списком
    cols = [d[0] for d in res.description]
    out = sys.stdout.buffer                                   # UTF-8 байты (Windows cp1251)
    out.write(("\t".join(cols) + "\n").encode("utf-8"))
    for row in res.fetchall():
        out.write(("\t".join("" if v is None else str(v) for v in row) + "\n").encode("utf-8"))
finally:
    os.unlink(tmp)                                            # уборка во всех ветках
```

---

## Паттерн 3: архивация в Parquet + чтение hot+cold tier

```python
# Запись cold tier (archive_jsonl_to_parquet.py): ZSTD — лучший ratio/speed.
con.execute(
    f"COPY (SELECT * FROM logs) TO '{archive_path}' "
    f"(FORMAT PARQUET, COMPRESSION ZSTD)"
)

# Чтение hot (JSONL) + cold (Parquet) одним view — union_by_name мирит дрейф.
parquets = "[" + ", ".join(f"'{p}'" for p in sorted(archive_dir.glob('*.parquet'))) + "]"
con.execute(
    "CREATE OR REPLACE VIEW logs AS "
    f"(SELECT * FROM read_json_auto('{tmp}', format='newline_delimited', union_by_name=true)) "
    f"UNION ALL BY NAME "
    f"(SELECT * FROM read_parquet({parquets}, union_by_name=true))"
)
```

---

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| `JSON transform error` / поле как `MAP(VARCHAR, DATE)` | issue #14259: DuckDB ≥1.1.x мисинферит mixed-type поля | явный `columns={...}` ЛИБО `sample_size=-1` ЛИБО pre-clean |
| Все данные в одной колонке `json` | `ignore_errors=true` при наличии битых строк схлопнул схему | pre-clean в Python (Паттерн 1), убрать `ignore_errors` |
| Поле есть в части строк → пропадает | дрейф схемы между событиями | `union_by_name=true` |
| `Binary file matches` при grep по stdout | вывод смешан с не-UTF-8 | писать `sys.stdout.buffer.write(...encode('utf-8'))` |
| Пустой результат с `WHERE col = 'x'` | значение вшито f-string'ом с неэкранированными кавычками | параметр `?` + `execute(sql, [val])` |
| `ignore_errors` «не работает» на массиве | он только для `newline_delimited` | для array-JSON — другой подход |

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| `read_json_auto(f, ignore_errors=true)` на «грязном» логе | схема схлопывается в одну `json`-колонку; тихая потеря данных (issue #14259) | pre-clean в Python + `union_by_name=true` без `ignore_errors` |
| `f"... WHERE store = '{user_val}'"` | SQL-инъекция + ломается на кавычках | `?`-плейсхолдер, значения списком в `execute` |
| `print(row)` для вывода с кириллицей | `UnicodeEncodeError` на Windows cp1251-pipe ([[feedback-windows-hook-stdout-cp1251]]) | `sys.stdout.buffer.write(s.encode("utf-8"))` |
| `import duckdb` на верхнем уровне без guard | хард-краш у того, кто не ставил duckdb | `_check_duckdb()` → graceful exit 2 |
| temp-файл без `finally`/`atexit` | leak temp-файлов при исключении в SQL | `finally: os.unlink` + `atexit` страховка |
| `quantile_cont` на больших логах | точный перцентиль дорог по памяти | `approx_quantile` (t-digest, достаточно для метрик) |

---

## Связанные скиллы

- **memory-unified** — готовые observability-отчёты (`memory_observability_query.py`/`_report.py`) поверх этих же паттернов; этот скилл — про сам DuckDB-слой, не redirect.
- **qdrant-operations** — для векторов/коллекций (DuckDB ≠ vector store).

## Реальные потребители в репозитории

`scripts/audit_query.py` · `scripts/memory_observability_query.py` · `scripts/skill_ingest_trend.py` · `scripts/archive_jsonl_to_parquet.py`
