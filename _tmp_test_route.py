"""Empirical review: over-recall->ask invariant + is_1c reachability. UTF-8 output to file."""
import io
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".claude", "hooks")
sys.path.insert(0, HOOKS)
from shared import pipeline_1c_bridge as m

buf = io.StringIO()


def out(*a):
    print(*a, file=buf)


out("=" * 70)
out("TEST 4: over-recall -> ask invariant (false-positive must NOT become confident)")
out("=" * 70)
out("Contract: confident_1c = JIRA OR _1C_STRONG.search(prompt). If only a")
out("domain-term+verb fired (no strong marker), flow MUST be ask_1c, never auto/gated.\n")

# These have a domain term + task verb but NO strong marker (no гкс_/config/dot/CamelCase/JIRA)
# -> must classify is_1c True (recall) BUT confident_1c False -> ask_1c
over_recall = [
    "создать отчёт в Notion",            # отчёт + создать, but it's Notion
    "добавить форму обратной связи на сайт",  # форму + добавить, web form
    "доработать документ Word с таблицами",   # документ+табличн+доработать, MS Word
    "настроить обмен сообщениями в чате",      # обмен + настроить
    "реализовать справочник терминов в вики",  # справочник + реализовать
]
all_ask = True
for p in over_recall:
    r = m.route_1c_task(p)
    ok = (r["is_1c"] and not r["confident_1c"] and r["flow"] == "ask_1c")
    all_ask = all_ask and ok
    out(f"  [{'OK ' if ok else '!!FAIL'}] is_1c={r['is_1c']} confident={r['confident_1c']} "
        f"flow={r['flow']:8} :: {p!r}")
out(f"\n  ALL degrade to ask_1c (not auto/gated): {all_ask}")

out("\n-- Counter: is there ANY domain-term+verb input that wrongly becomes confident? --")
out("   confident requires JIRA or _1C_STRONG. _1C_STRONG = гкс_|config|obj.dot|CamelCase.")
out("   A plain term like 'отчёт'/'документ' (lowercase, no dot) does NOT match _1C_STRONG:")
for w in ["отчёт", "документ", "справочник", "регистр", "форма", "обработка"]:
    out(f"     _1C_STRONG.search({w!r:14}) = {bool(m._1C_STRONG.search(w))}")

out("\n" + "=" * 70)
out("TEST 5: is_1c logic reachable & correct")
out("=" * 70)

reach = [
    # (prompt, expect_is_1c, note)
    ("гкс_РасчетКвот", True, "definitive гкс_ alone, NO verb -> is_1c (intentional)"),
    ("configuration/260304/docs/spec.md", True, "definitive config path, no verb"),
    ("GKSTCPLK-2182", True, "JIRA alone -> is_1c"),
    ("что такое ТабличныйДокумент", False,
     "CamelCase strong but NO verb -> is_1c False (question)"),
    ("как работает RAG", False, "no signal, no verb -> False"),
    ("напиши скрипт python", False, "verb 'напиши'? no -> check; no 1C signal -> False"),
    ("доработать форму документа Расход", True,
     "domain term + verb -> is_1c True (miss-case from unit)"),
    ("исправить ошибку в проведении документа", True, "T2 bugfix path"),
    ("это не учтено при тестировании функционала", True, "T3 path"),
]
all_reach = True
for p, exp, note in reach:
    r = m.classify_1c_task(p)
    ok = r["is_1c"] == exp
    all_reach = all_reach and ok
    out(f"  [{'OK ' if ok else '!!FAIL'}] is_1c={r['is_1c']!s:5} ttype={str(r['ttype']):4} "
        f"ask={r['ask']!s:5} :: {p!r}")
    if not ok:
        out(f"          ^ expected {exp} -- {note}")

out(f"\n  ALL reachability cases correct: {all_reach}")

out("\n-- ttype branch reachability --")
for p in ["это не учтено", "найдено при тестировании функционала", "исправить ошибку",
          "доработать форму"]:
    r = m.classify_1c_task(p + " документа")
    out(f"     {p!r:42} -> ttype={r['ttype']}")

out("\n-- 'definitive without verb' vs 'question without verb' (point 5) --")
out(f"   'гкс_X' (definitive, no verb)            -> is_1c={m.classify_1c_task('гкс_X')['is_1c']}")
out(f"   'что такое ТабличныйДокумент' (strong,no verb) -> "
    f"is_1c={m.classify_1c_task('что такое ТабличныйДокумент')['is_1c']}")

# write UTF-8
sys.stdout.buffer.write(buf.getvalue().encode("utf-8"))
