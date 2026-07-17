# 02 — Дизайн: починка двух нулей

Принцип: чиним **механизм**, а не показание прибора. Каждая правка обязана быть
верной сама по себе, даже если бы критерия не существовало.

## Правка 1 — `session-memory-save.py`: погашенный дубль обязан оставлять след

**Файл:** [`.claude/hooks/session-memory-save.py`](../../.claude/hooks/session-memory-save.py)

`_record_ingest` получает `**kw` (проброс в `record_ingest`, который уже принимает
`reason` и `**extra`):

```python
def _record_ingest(action, content_hash="", **kw):
    ...
    record_ingest("memory_ai", action, content_hash=content_hash,
                  harvester="session-memory-save", **kw)
```

Путь раннего выхода (строка ~452) эмитит событие:

```python
if already_saved(ctx["session_id"]):
    _emit_langfuse_span(ctx, status="skipped-duplicate")
    _record_ingest("dup", _content_hash(format_summary(ctx)),
                   reason="session_already_saved")
    return None
```

### Обоснование выбора action=`dup` (судейское решение)

`ACTIONS` в [`ingest_metrics.py:18`](../../src/memory/orchestrator/ingest_metrics.py)
описывает `dup` как «skipped: content_hash already present (anti-flood / idempotency)».
Здесь ключ дедупа — `session_id`, а не `content_hash`. Формально ключ другой,
семантика **та же**: запись погашена, потому что эквивалент уже есть.
Прецедент: `save_important_message` дедупит по content-equality и эмитит `dup`;
`capture_pattern` дедупит по pending+saved и эмитит `dup`. Ключ фиксируем честно
через `reason="session_already_saved"`.

Альтернатива `action="skipped"` отвергнута: она смешала бы идемпотентность с
gated-скипами (confidence floor, cap) и оставила бы дедуп невидимым в
`dup_rate` дашборда — то есть не починила бы исходную дыру.

**Цена:** на dedup-пути добавляются `format_summary` + `_content_hash` (~мс,
оба уже зовутся в `save_to_sqlite`). Stop-бюджет не страдает. Оба fail-soft.

## Правка 2 — `reflection.py`: достижимый триггер

**Файл:** [`.claude/hooks/shared/reflection.py`](../../.claude/hooks/shared/reflection.py)

`DEFAULT_MIN_CLUSTER = 3` → `2`, с комментарием-заземлением на замер
(макс. реальный кластер = 2 на корпусе из 52 эпизодов → 3 недостижим).

Консолидация кластера из 2 near-duplicate эпизодов — это ровно то, что модуль
декларирует в docstring: «fold them into a single pattern instead of N
near-duplicates». При N=2 схлопывание двух почти-дублей корректно.

`sim_threshold` **не трогаем** (0.5): понижение множит ложные склейки.

## Правка 3 — `reflect_memory.py`: один источник дефолтов

**Файл:** [`scripts/reflect_memory.py`](../../scripts/reflect_memory.py)

argparse-дефолты (`3` / `0.5` / `10`) — хардкод-копии констант модуля. Каденс идёт
через CLI, поэтому копия в CLI и есть операционное значение; правка модуля без
этого — no-op. Импортируем константы:

```python
from shared.reflection import (
    DEFAULT_CAP, DEFAULT_MIN_CLUSTER, DEFAULT_SIM_THRESHOLD, make_link_fn, reflect,
)
...
ap.add_argument("--min-cluster", type=int, default=DEFAULT_MIN_CLUSTER, ...)
ap.add_argument("--sim", type=float, default=DEFAULT_SIM_THRESHOLD, ...)
ap.add_argument("--cap", type=int, default=DEFAULT_CAP, ...)
```

Для `sim`/`cap` behavior-preserving (значения совпадают); устраняет дрейф.

## Правка 4 — `memory_maintenance.py`: apply для одного джоба

**Файл:** [`scripts/memory_maintenance.py`](../../scripts/memory_maintenance.py)

Сегодня `_run_subprocess` знает только глобальный `apply`. Добавляем per-job
opt-in override:

```python
def _job_apply(name: str, apply: bool) -> bool:
    """Effective apply for one job: global --apply, or a per-job env opt-in.

    Exists so one job can be granted write rights without handing them to all
    five: MEMORY_MAINTENANCE_APPLY=1 would also let promote write docs/wiki and
    reindex_* rewrite production wiki_pages_v1 / skill_library.
    """
    if apply:
        return True
    return os.environ.get(f"MEMORY_MAINTENANCE_APPLY_{name.upper()}") == "1"
```

`_run_subprocess` вычисляет `apply = _job_apply(name, apply)` **первой строкой** —
до проверки `apply_only`, чтобы override работал и для apply-only джобов.

Имя `MEMORY_MAINTENANCE_APPLY_<JOB>` (не `REFLECT_APPLY`) — согласовано с
существующим `MEMORY_MAINTENANCE_APPLY` и обобщается на все 5 джобов без
спец-кейса на reflect.

**Обратная совместимость:** env не задан → выражение False → поведение
бит-в-бит прежнее.

## Правка 5 — включение

**Файл:** `.claude/settings.local.json` (gitignored, локально — как `TDD_GUARD_ENABLE`)

```json
"MEMORY_MAINTENANCE_APPLY_REFLECT": "1"
```

Остальные 4 джоба остаются dry-run.

## Ожидаемый эффект (проверяемый)

- reflect: `clusters_triggered` 0 → **2**, `created` → 2 паттерна,
  DERIVES_FROM → **4 ребра** (2 кластера × 2 эпизода) → `reflection>=1` = OK **по факту**.
- dup: первая же повторная Stop-сессия даёт `store=memory_ai action=dup` →
  `dup_nonzero` = OK по факту.

## Риски

| Риск | Митигация |
|---|---|
| `min_cluster=2` начнёт схлопывать не-дубли | `sim=0.5` не тронут — 50% overlap токенов = near-duplicate; `cap=10` ограничивает прогон |
| reflect пишет в production `learned_patterns` | content_hash-дедуп (`skipped_dup`) → повторный прогон идемпотентен; §22 archive-not-delete обратим |
| `dup`-эмит удлиняет Stop-путь | fail-soft, ~мс, обе функции уже на соседнем пути |
| Тесты пинят `min_cluster=3` | Проверено: все 6 тестов передают `min_cluster` **явно** → дефолт ничем не запинен. Добавляем тест на новый дефолт. |

## Проверка

- unit: новый дефолт; dup-эмит на dedup-пути; `_job_apply` (3 ветки).
- **саботаж** ([[feedback-sabotage-check-tests]]): откатить каждую правку → тест обязан покраснеть.
- live: `reflect_memory.py` dry-run → ожидаем `clusters_triggered=2`; затем `--apply`.
- `code-verify` субагентом (read-only).
