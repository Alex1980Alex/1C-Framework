#!/usr/bin/env python3
"""edt_journal.py — журнал EDT как источник ИСТИНЫ об исходе MCP-вызова.

Зачем. Метрики tool-health считают честным провалом вызова **непарный Pre** (платформа
не шлёт PostToolUse на неуспешный вызов — NB1, roadmap 260718). У долгих операций EDT это
врёт: клиент обрывает ожидание на ~60с, а операция на стороне EDT завершается УСПЕШНО
(замер 2026-07-25: `create_project` 60 253мс, `delete_project` 134 035/203 137мс,
`update_database` 119 398/215 360/3 147 392мс — все `outcome=ok`). Такой вызов — не дефект
инструмента, а клиентский потолок, и вердикт broken/degraded по нему ложный. Единственный
источник, различающий «упало» и «клиент не дождался», — журнал EDT.

Формат (плагин `com.ditrix.edt.mcp.server` пишет в `<workspace>/.metadata/.log`, ротация
в `.bak_N.log`). Время локальное naive и несёт его ПРЕДШЕСТВУЮЩАЯ строка `!ENTRY`:

    !ENTRY com.ditrix.edt.mcp.server 1 0 2026-07-23 13:10:57.123
    !MESSAGE Completed tools/call: update_database in 3147392ms, outcome=ok
    !ENTRY com.ditrix.edt.mcp.server 2 0 2026-07-24 18:16:12.375
    !MESSAGE Failed tools/call: delete_project - Project not found: гкс_Эмуляция…

Время НАЧАЛА вызова = таймстемп `Completed` − длительность; сверено с hook-логом:
Δ(journal.start − Pre.ts) на 22 живых записях = +0.065…+0.548с — этого хватает для
сопоставления с точностью до вызова (допуск `SERVER_OK_MATCH_SEC` в tool_effectiveness).
`Failed tools/call` несёт ТЕКСТ отказа, которого нет ни в hook-логе, ни в native OTel.

stdlib-only, read-only, fail-soft: нет каталогов/файла/битая строка → просто меньше
записей (никогда не исключение) — потребитель работает как раньше, лишь без вычета.

Запуск: python scripts/edt_journal.py [--days 14] [--min-ms 55000] [--tool update] [--failures]
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: где искать журналы: каждый EDT-воркспейс — свой `.metadata/.log` (+ архивы ротации)
JOURNAL_GLOBS = ("*/.metadata/.log", "*/.metadata/*.bak*.log")

#: bundle плагина MCP в EDT. На живых журналах `tools/call` пишет ТОЛЬКО он, но полагаться
#: на это нельзя: в один `.metadata/.log` пишут все плагины воркспейса, а имена инструментов
#: у `edt-mcp` и `codepilot1c` массово пересекаются (`create_metadata`, `debug_status`,
#: `validate_query`…) — чужая долгая запись «оправдала» бы провал не своего сервера.
#: Сверяем по ПРЕФИКСУ: под-бандлы (`…mcp.server.core`) остаются своими, а смена id
#: у апстрима просто выключит вычет (fail-soft), но не даст ложного.
BUNDLE_PREFIX = "com.ditrix.edt.mcp"

_TS_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

# дробная часть — `\d+`, а не фиксированные 3 знака: точность лога = деталь реализации Eclipse
_ENTRY_RE = re.compile(
    r"^!ENTRY\s+(?P<bundle>\S+)\s+\d+\s+\d+\s+(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)"
)
_COMPLETED_RE = re.compile(
    r"^!MESSAGE\s+Completed\s+tools/call:\s*(?P<tool>\S+)\s+in\s+"
    r"(?P<ms>\d+)ms,\s*outcome=(?P<outcome>\w+)"
)
_FAILED_RE = re.compile(r"^!MESSAGE\s+Failed\s+tools/call:\s*(?P<tool>\S+)\s*-\s*(?P<text>.*)$")


def find_journals(root: Path | None = None) -> list[Path]:
    """Журналы EDT в репозитории: основной лог каждого воркспейса + архивы ротации."""
    base = root if root is not None else ROOT
    result: list[Path] = []
    for pattern in JOURNAL_GLOBS:
        try:
            result.extend(sorted(base.glob(pattern)))
        except OSError:
            continue
    return result


def _parse_ts(raw: str) -> datetime | None:
    """Таймстемп `!ENTRY` → naive datetime; None при неразборе (fail-soft)."""
    try:
        return datetime.strptime(raw, _TS_FORMAT)
    except ValueError:
        return None


def parse_journal(
    text: str, source: str = "", bundle_prefix: str = BUNDLE_PREFIX
) -> tuple[list[dict], list[dict]]:
    """Содержимое журнала → (завершённые вызовы, тексты отказов).

    Завершённый: ``{tool, start, end, ms, outcome, source}`` (``start`` = ``end − ms``).
    Отказ: ``{tool, ts, text, source}``.

    Берутся ТОЛЬКО записи бандла ``bundle_prefix`` (см. его комментарий: в общий журнал
    пишут все плагины, а имена тулов пересекаются). Битый таймстемп `!ENTRY` обнуляет
    контекст: последующие `!MESSAGE` пропускаются до следующего корректного `!ENTRY` —
    лучше потерять запись, чем приписать ей чужое время (или чужой бандл).
    """
    completed: list[dict] = []
    failures: list[dict] = []
    current_ts: datetime | None = None

    for line in text.splitlines():
        entry = _ENTRY_RE.match(line)
        if entry:
            ours = entry.group("bundle").startswith(bundle_prefix)
            current_ts = _parse_ts(entry.group("ts")) if ours else None
            continue
        if current_ts is None:
            continue

        done = _COMPLETED_RE.match(line)
        if done:
            ms = int(done.group("ms"))
            try:
                start = current_ts - timedelta(milliseconds=ms)
            except (OverflowError, OSError, ValueError):
                # Абсурдная длительность (порча лога) → пропускаем запись, а не роняем
                # прогон: класс бага tz-крэша iter_window_rows, где одна строка убивала всё.
                continue
            completed.append(
                {
                    "tool": done.group("tool"),
                    "start": start,
                    "end": current_ts,
                    "ms": ms,
                    "outcome": done.group("outcome"),
                    "source": source,
                }
            )
            continue

        failed = _FAILED_RE.match(line)
        if failed:
            failures.append(
                {
                    "tool": failed.group("tool"),
                    "ts": current_ts,
                    "text": failed.group("text").strip(),
                    "source": source,
                }
            )
    return completed, failures


def read_journals(
    since: datetime | None = None,
    journals: list[Path] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Все журналы → (завершённые, отказы) за окно ``since``, отсортированные по времени.

    Нечитаемый файл пропускается молча. ``source`` = имя воркспейса (`<ws>/.metadata/.log`)
    — в отчёте видно, ГДЕ исполнялся вызов.
    """
    # dict.fromkeys — дедуп путей: один и тот же журнал дважды = удвоение записей,
    # а значит и удвоение вычета у потребителя
    paths = list(dict.fromkeys(journals if journals is not None else find_journals()))
    all_completed: list[dict] = []
    all_failures: list[dict] = []

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        completed, failures = parse_journal(text, source=path.parent.parent.name)
        all_completed += [r for r in completed if since is None or r["end"] >= since]
        all_failures += [r for r in failures if since is None or r["ts"] >= since]

    all_completed.sort(key=lambda r: r["end"])
    all_failures.sort(key=lambda r: r["ts"])
    return all_completed, all_failures


def server_ok_calls(
    since: datetime | None = None,
    min_ms: int = 0,
    journals: list[Path] | None = None,
) -> dict[str, list[tuple[datetime, int]]]:
    """Успешные на сервере вызовы длительностью ≥ ``min_ms``, по короткому имени тула.

    Именно это — доказательство «клиент не дождался, а операция прошла»: ``outcome=ok``
    при длительности выше клиентского потолка. Значение — список ``(start, ms)``
    по возрастанию времени (у потребителя сопоставление расходуемое, 1:1).
    """
    completed, _ = read_journals(since=since, journals=journals)
    result: dict[str, list[tuple[datetime, int]]] = {}
    for r in completed:
        if r["outcome"] != "ok" or r["ms"] < min_ms:
            continue
        result.setdefault(r["tool"], []).append((r["start"], r["ms"]))
    for calls in result.values():
        calls.sort(key=lambda pair: pair[0])
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Журнал EDT: исходы вызовов MCP-плагина")
    ap.add_argument("--days", type=int, default=14, help="окно, дней (по умолч. 14)")
    ap.add_argument("--min-ms", type=int, default=0, help="только вызовы не короче, мс")
    ap.add_argument("--tool", default="", help="фильтр по имени тула (подстрока)")
    ap.add_argument("--failures", action="store_true", help="показать тексты отказов")
    args = ap.parse_args(argv)

    since = datetime.now() - timedelta(days=args.days)
    completed, failures = read_journals(since=since)
    print(f"журналов: {len(find_journals())}; записей за {args.days}д: {len(completed)}")
    for r in completed:
        if (args.tool and args.tool not in r["tool"]) or r["ms"] < args.min_ms:
            continue
        print(
            f"  {r['end']:%m-%d %H:%M:%S} {r['tool']:<28} {r['ms']:>9}ms "
            f"outcome={r['outcome']:<6} [{r['source']}]"
        )
    if args.failures:
        print(f"\nотказов: {len(failures)}")
        for r in failures:
            if args.tool and args.tool not in r["tool"]:
                continue
            print(f"  {r['ts']:%m-%d %H:%M:%S} {r['tool']}: {r['text'][:150]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
