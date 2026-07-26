#!/usr/bin/env python3
"""Общий rule-слой эффективности инструментов (roadmap 260713 P2.2).

Детерминированные метрики эффективности по консенсусу 2026 (OTel GenAI +
deepeval/MCP-Bench), вынесенные в single-source из дублирующих реализаций
`scripts/tool_usage_report.py` и `scripts/analyze_tool_health.py`:

  - **pair_durations** — реальная латентность вызова (Pre→Post-пара, join по
    ``tool_call_id`` иначе FIFO; tz-guard как в Sonar parse_dt);
  - **percentile** — p50/p95 без numpy;
  - **effectiveness_from_posts** — retry (`repeats`, тот же ``args_hash``) vs
    abandonment (последняя попытка тула — ошибка);
  - **step_efficiency** — доля избыточных вызовов (repeats/calls);
  - **rollup_by_server** — Tool Success Rate + эффективность per-server (MCP
    группируются по ``mcp__<server>__<op>``; built-in — общая корзина).

stdlib-only (без numpy/duckdb) — используется в detached Stop-хук-контексте.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

BUILTIN_BUCKET = "(built-in)"

# Канонические категории строк-вызовов (одна пара Pre/Post на вызов). Единый источник
# для всех потребителей (analyze_tool_health / tool_usage_report / audit_query) —
# N-P2.3: раньше дублировалось как локальный литерал/константа в каждом.
CANONICAL_CATEGORIES = ("mcp_call", "tool_call")


def parse_ts(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def percentile(values: list[int], q: float) -> float:
    """Перцентиль (linear interpolation), q ∈ [0,1]. stdlib, без numpy."""
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    idx = q * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def pair_durations(pres: list[dict], posts: list[dict]) -> list[int]:
    """Список реальных длительностей Pre→Post (мс). Join по ``tool_call_id``,
    иначе FIFO (ранний неиспользованный Pre не позже Post). tz-guard: naive vs
    aware вычитание бросает TypeError (класс бага Sonar parse_dt) — пропускаем."""
    if not posts:
        return []
    pres_sorted = sorted(pres, key=lambda e: e.get("ts", ""))
    posts_sorted = sorted(posts, key=lambda e: e.get("ts", ""))
    pre_by_id: dict[str, dict] = {}
    for p in pres_sorted:
        cid = p.get("tool_call_id")
        if cid:
            pre_by_id.setdefault(cid, p)
    used: set[int] = set()
    out: list[int] = []
    for post in posts_sorted:
        pre = None
        cid = post.get("tool_call_id")
        if cid and cid in pre_by_id and id(pre_by_id[cid]) not in used:
            pre = pre_by_id[cid]
        else:
            for p in pres_sorted:
                if id(p) in used:
                    continue
                if p.get("ts", "") <= post.get("ts", ""):
                    pre = p
                    break
        if pre is None:
            continue
        a, b = parse_ts(pre.get("ts")), parse_ts(post.get("ts"))
        if a and b:
            try:
                d = int((b - a).total_seconds() * 1000)
            except (TypeError, ValueError):
                continue
            if d >= 0:
                used.add(id(pre))  # помечаем Pre использованным ТОЛЬКО при валидной паре
                out.append(d)
    return out


def _direct_duration(e: dict) -> int | None:
    """Прямой ``duration_ms`` из Post-строки (260718 H-P0.1), если валиден.
    None → строка старого формата (до захвата) / не число / отрицательное."""
    v = e.get("duration_ms")
    if isinstance(v, bool):  # bool ⊂ int, но не длительность
        return None
    if isinstance(v, (int, float)) and v >= 0:
        return int(v)
    return None


def tool_durations(pres: list[dict], posts: list[dict]) -> list[int]:
    """Длительности вызовов (мс), ПРЕДПОЧИТАЯ прямой ``duration_ms`` из payload
    (260718 H-P0.1) паре Pre→Post.

    Прямое поле точнее: платформенная длительность самого тула, без overhead'а
    хука и без FIFO-эвристики пэйринга. Смешанный режим: Post со свежим полем
    берётся напрямую, Post старого формата (поля нет) добирается ``pair_durations``
    от непотраченных Pre. Полностью behavior-preserving на исторических данных
    (ни одной строки с ``duration_ms`` → результат == ``pair_durations``).
    """
    if not posts:
        return []
    direct: list[int] = []
    no_field: list[dict] = []
    for po in posts:
        d = _direct_duration(po)
        if d is not None:
            direct.append(d)
        else:
            no_field.append(po)
    if not no_field:
        return direct  # все посты несут прямую длительность — пэйринг не нужен
    # Хвост без поля добираем пэйрингом. Pre, «съеденные» прямыми постами, для FIFO
    # не исключаем (их tool_call_id всё равно матчнётся к своему Post, а лишние ранние
    # Pre безвредны — pair_durations берёт самый ранний ≤ Post и валидирует дельту).
    return direct + pair_durations(pres, no_field)


def _naive(ts: datetime) -> datetime:
    """Aware → локальный naive (класс бага Sonar parse_dt: naive-vs-aware вычитание
    бросает TypeError). Единая нормализация для сравнений с naive ``now``."""
    if ts.tzinfo is not None:
        try:
            return ts.astimezone().replace(tzinfo=None)
        except (ValueError, OSError, OverflowError):
            return ts.replace(tzinfo=None)
    return ts


BLOCK_MATCH_SEC = 5  # блок и canonical Pre — соседи в одной Pre-цепочке (мс-разрыв)
# Серверная запись об исходе и Pre — тот же вызов: замер 2026-07-25 на 22 живых записях
# журнала EDT дал Δ(journal.start − Pre.ts) = +0.065…+0.548с. Допуск 2с с запасом, но
# сильно уже BLOCK_MATCH_SEC: чем он шире, тем выше риск приписать запись чужому вызову.
SERVER_OK_MATCH_SEC = 2


def is_guard_block(e: dict) -> bool:
    """Запись лога = блокировка энфорсера: вызов ОТКЛОНЁН, инструмент не исполнялся.

    Единое определение для обоих слоёв: report (``guard_blocks_by_tool`` — блок не провал
    инструмента) и enforcement (``pipeline-protocol-stop`` — блок не ПРАВКА кода). ``tool``
    обязателен: Stop-хуки блокируют без инструмента, к вызову их не привязать."""
    return (
        isinstance(e, dict)
        and e.get("category") == "hook"
        and e.get("event") == "PreToolUse"
        and e.get("outcome") == "block"
        and bool(e.get("tool"))
    )


def completion_stats(
    pres: list[dict],
    posts: list[dict],
    now: datetime | None = None,
    grace_sec: int = 120,
    blocked: list[tuple[str, datetime]] | None = None,
    blocked_ids: set[str] | None = None,
    server_ok: list[tuple[datetime, int]] | None = None,
    server_ok_ids: set[str] | None = None,
) -> dict:
    """Честный сигнал незавершения built-in вызова из НЕПАРНЫХ Pre (roadmap 260718 N-P0.1).

    **Корень NB1:** платформа НЕ шлёт ``PostToolUse`` на неуспешный built-in вызов
    (Bash non-zero exit, Edit «строка не найдена», Read miss — эмпирически
    подтверждено дампом формы 2026-07-18). Post есть ТОЛЬКО у успешных вызовов →
    ``outcome`` Post-строки почти всегда ``allow`` → error-rate из Post ≡ 0.
    Единственный честный сигнал провала built-in = **Pre без парного Post**.

    ⚠ **Блоки хуков ПОПАДАЮТ сюда** (замер 2026-07-25 опроверг прежнее «exit 2
    преемптит canonical-логгер, Write unpaired=0 при живом блоке»): из 49 непарных
    Write 36 совпали по (сессия, тул, ±5с) с block-записью энфорсера, а native OTel
    не знает о них вовсе — тул не исполнялся. Часть энфорсеров блокирует через
    ``decision:"block"``, при котором Pre-цепочка доходит до логгера. Поэтому
    вызывающий передаёт ``blocked`` — отклонённые вызовы уходят в отдельный счётчик,
    а не в ``failed`` (иначе активность гардов читается как поломка инструмента).

    ⚠ **Две цифры про один и тот же эффект, не путать** (примирение N2, ретро 260725):
    **36 из 49** — разведочный замер: непарные Pre, у которых НЕТ события в native OTel
    И рядом (та же сессия, ±5с) есть block-запись; знаменатель — окно замера.
    **44 из 46** — фактический вычет этой функции на окне 14д: сопоставление
    расходуемое 1:1 (один блок объясняет РОВНО один непарный Pre), знаменатель —
    ``incomplete`` того же окна. Числа не сравнимы напрямую: разные знаменатели и
    разные критерии (native-absence vs consumable-матчинг). Совпадает вывод, а не
    величина: остаток непарных Write после вычета = 2, и это ровно те два вызова,
    где native говорит ``success=true`` (потерянный Post) — две методики сошлись
    независимо.

    ⚠ **Клиентский потолок — второй класс ложного провала** (260725, тот же приём вычета):
    у долгой операции клиент обрывает ожидание (~60с) и Post не приходит, ХОТЯ на сервере
    вызов завершился успешно — журнал EDT показал `outcome=ok` при 60 253мс
    (``create_project``), 134 035/203 137мс (``delete_project``), 119 398/215 360/3 147 392мс
    (``update_database``). Дефекта инструмента тут нет, поэтому вызывающий передаёт
    ``server_ok`` — список ``(start, ms)`` подтверждённых сервером успехов (см.
    ``edt_journal.server_ok_calls``), и такие непарные Pre уходят в счётчик
    ``client_timeout``, а не в ``failed``. Отличие от ``blocked``: там тул НЕ исполнялся,
    здесь исполнился и УСПЕШНО — потерян лишь ответ. Оба остаются видимы в отчёте:
    вычитается вердикт, а не факт.

    Пары считаются по ``tool_call_id`` (в проде заполнен всегда), непарные посты
    добираются FIFO по ts. Непарные Pre моложе ``grace_sec`` от ``now`` =
    ``in_flight`` (Post ещё может прийти) и в провал НЕ идут.

    Возвращает ``{completed, failed, in_flight, blocked, client_timeout}`` (Pre-сторона;
    ``completed`` = число Pre, получивших Post — для сверки, аналитика берёт ``len(posts)``).
    ``blocked``/``client_timeout`` нулевые без соответствующего аргумента → поведение
    бит-в-бит прежнее. ``blocked_ids``/``server_ok_ids`` (опц.) — сюда складываются
    ``tool_call_id`` объяснённых вызовов: нужно тем, кто считает ту же выборку ВТОРЫМ
    разрезом (``agent_rollup``), чтобы одно объяснение не списалось дважды — расходуемый
    список у каждого вызова свой (копия).
    """
    now = _naive(now) if now is not None else datetime.now()
    pres_sorted = sorted(pres, key=lambda e: e.get("ts", ""))

    # 1) парность по id
    paired_idx: set[int] = set()
    pre_by_id: dict[str, list[int]] = defaultdict(list)
    for i, p in enumerate(pres_sorted):
        cid = p.get("tool_call_id")
        if cid:
            pre_by_id[cid].append(i)
    posts_no_id = 0
    for po in posts:
        cid = po.get("tool_call_id")
        if cid and pre_by_id.get(cid):
            paired_idx.add(pre_by_id[cid].pop(0))
        else:
            posts_no_id += 1
    # 2) посты без id-совпадения добираем FIFO (самый ранний непарный Pre)
    if posts_no_id:
        for i in range(len(pres_sorted)):
            if posts_no_id <= 0:
                break
            if i not in paired_idx:
                paired_idx.add(i)
                posts_no_id -= 1

    failed = in_flight = blocked_n = client_timeout = 0
    unused_blocks = list(blocked or [])
    unused_server_ok = list(server_ok or [])

    # ПЕРВЫЙ проход: парные (успешно вернувшиеся) вызовы забирают свои серверные записи —
    # безусловно, до всякого непарного. Иначе порядок решал бы исход: непарный Pre, стоящий
    # РАНЬШЕ парного, съел бы его запись (в проде недостижимо — парные короче потолка, — но
    # инвариант не должен зависеть от эмпирики).
    if unused_server_ok:
        for i, p in enumerate(pres_sorted):
            if i not in paired_idx:
                continue
            pts = parse_ts(p.get("ts"))
            if pts is not None:
                _take_server_ok(unused_server_ok, _naive(pts))

    for i, p in enumerate(pres_sorted):
        if i in paired_idx:
            continue
        pts = parse_ts(p.get("ts"))
        cid = p.get("tool_call_id") or ""
        if pts is not None and (now - _naive(pts)).total_seconds() < grace_sec:
            in_flight += 1  # Post ещё может прийти — не считаем провалом
        elif pts is not None and take_block(unused_blocks, p.get("session") or "", _naive(pts)):
            blocked_n += 1  # вызов отклонён гардом — тул не исполнялся
            # Пустой id в множество НЕ кладём: второй разрез сопоставляет по членству, и один
            # `""` списал бы ВСЕ безыдентификаторные вызовы группы (провалы бы исчезли).
            # Цена — второй разрез недосчитает это объяснение; недовычет безопаснее перевычета.
            if blocked_ids is not None and cid:
                blocked_ids.add(cid)
        elif pts is not None and _take_server_ok(unused_server_ok, _naive(pts)):
            client_timeout += 1  # сервер завершил успешно — клиент не дождался ответа
            if server_ok_ids is not None and cid:
                server_ok_ids.add(cid)
        else:
            failed += 1
    return {
        "completed": len(paired_idx),
        "failed": failed,
        "in_flight": in_flight,
        "blocked": blocked_n,
        "client_timeout": client_timeout,
    }


def take_block(blocks: list[tuple[str, datetime]], session: str, ts: datetime) -> bool:
    """Снять из ``blocks`` запись, объясняющую вызов в ``ts`` (та же сессия, ±окно).

    Расходуемое сопоставление 1:1 — один блок объясняет РОВНО один непарный Pre,
    иначе одна block-запись «оправдала» бы серию реальных провалов. ``tool_call_id``
    у block-записей пуст, поэтому ключ — (сессия, близость по времени)."""
    for idx, (b_session, b_ts) in enumerate(blocks):
        if b_session == session and abs((b_ts - ts).total_seconds()) <= BLOCK_MATCH_SEC:
            blocks.pop(idx)
            return True
    return False


_take_block = take_block  # обратно-совместимый алиас (внутренний call-site + тесты)


def _take_server_ok(records: list[tuple[datetime, int]], ts: datetime) -> bool:
    """Снять из ``records`` серверный успех, объясняющий вызов, начатый в ``ts``.

    Расходуемое сопоставление 1:1 (как у блоков): одна запись объясняет РОВНО один
    вызов, иначе один долгий успех «оправдал» бы серию реальных провалов. Ключ — только
    близость по времени начала: ``tool_call_id`` серверу неизвестен, а имя тула уже
    учтено вызывающим (список приходит per-tool).
    """
    for idx, (start, _ms) in enumerate(records):
        if abs((start - ts).total_seconds()) <= SERVER_OK_MATCH_SEC:
            records.pop(idx)
            return True
    return False


def _is_error_post(e: dict) -> bool:
    return e.get("outcome") == "error" or bool(e.get("error"))


def effectiveness_from_posts(posts: list[dict]) -> dict:
    """retry/abandonment по завершённым Post одного инструмента.

    ``repeats`` — повтор идентичного вызова (тот же ``args_hash`` = retry).
    ``abandonment`` — последняя (по ts) попытка тула завершилась ошибкой (не
    восстановились). ⚠ у built-in тулов детект ошибки best-effort (Bash non-zero
    exit не всегда помечается) → метрики built-in консервативны.
    """
    ordered = sorted(posts, key=lambda e: e.get("ts", ""))
    seen: set = set()
    repeats = 0
    for e in ordered:
        ah = e.get("args_hash")
        if ah:
            if ah in seen:
                repeats += 1
            seen.add(ah)
    abandonment = bool(ordered) and _is_error_post(ordered[-1])
    return {"repeats": repeats, "abandonment": abandonment}


def step_efficiency(calls: int, repeats: int) -> float:
    """Доля избыточных вызовов (retry) в общем числе вызовов, ∈ [0,1].
    0 = ни одного повтора; выше = хуже (больше потраченных шагов)."""
    if calls <= 0:
        return 0.0
    return round(repeats / calls, 4)


def server_of(tool: str | None) -> str:
    """MCP-сервер инструмента: ``mcp__<server>__<op>`` → ``<server>``.
    Built-in/нативные (Read/Bash/Edit/…) → общая корзина ``(built-in)``."""
    t = tool or ""
    if t.startswith("mcp__") and "__" in t[5:]:
        return t[5:].split("__", 1)[0]
    return BUILTIN_BUCKET


def rollup_by_server(tools_stats: dict[str, dict]) -> dict[str, dict]:
    """Агрегат per-server из per-tool статистики (выход aggregate_tools).

    Каждой группе: calls / errors / success / success_rate / error_rate /
    repeats / step_efficiency / abandonment_tools (сколько тулов группы брошены
    на ошибке) / tools (число инструментов). unused-тулы (0 вызовов) не искажают
    success_rate — их calls=0 не добавляют веса.
    """
    agg: dict[str, dict] = defaultdict(
        lambda: {
            "calls": 0,
            "errors": 0,
            "repeats": 0,
            "abandonment_tools": 0,
            "tools": 0,
        }
    )
    for tool, st in tools_stats.items():
        g = agg[server_of(tool)]
        g["calls"] += int(st.get("calls", 0))
        g["errors"] += int(st.get("errors", 0))
        g["repeats"] += int(st.get("repeats", 0))
        g["tools"] += 1
        if st.get("abandonment"):
            g["abandonment_tools"] += 1
    out: dict[str, dict] = {}
    for server, g in agg.items():
        calls = g["calls"]
        success = calls - g["errors"]
        out[server] = {
            **g,
            "success": success,
            "success_rate": round(success / calls, 4) if calls else 1.0,
            "error_rate": round(g["errors"] / calls, 4) if calls else 0.0,
            "step_efficiency": step_efficiency(calls, g["repeats"]),
        }
    return out


__all__ = [
    "BUILTIN_BUCKET",
    "parse_ts",
    "percentile",
    "pair_durations",
    "tool_durations",
    "completion_stats",
    "effectiveness_from_posts",
    "step_efficiency",
    "server_of",
    "rollup_by_server",
]
