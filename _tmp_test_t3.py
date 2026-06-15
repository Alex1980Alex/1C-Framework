"""Probe: T3 'found-in-testing' phrasing without an explicit task verb."""
import io
import os
import sys

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".claude", "hooks")
sys.path.insert(0, HOOKS)
from shared import pipeline_1c_bridge as m

buf = io.StringIO()


def out(*a):
    print(*a, file=buf)


# T3 = "не учтено" / found-in-testing. Does the typical phrasing carry a task verb?
t3_phrasings = [
    "это не учтено при тестировании функционала",      # NO verb
    "при тестировании функционала не учтено поле X",   # NO verb
    "не учли проведение в документе",                  # 'не учли'? not in _TASK_VERB
    "нужно доработать: при тестировании не учтено проведение",  # HAS 'доработать'
    "обнаружили при тестировании что справочник не учтён, добавить колонку",  # HAS 'добавить'
    "функционал не учтён, исправить",                  # HAS 'исправить' (but is it ошибк? -> T2 check)
]
out("T3 phrasings -- is_1c + ttype + whether a _TASK_VERB fired:")
for p in t3_phrasings:
    r = m.classify_1c_task(p)
    has_verb = bool(m._TASK_VERB.search(p))
    has_sig = bool(m._1C_SIGNAL.search(p))
    has_strong = bool(m._1C_STRONG.search(p))
    out(f"  is_1c={r['is_1c']!s:5} ttype={str(r['ttype']):4} verb={has_verb!s:5} "
        f"sig={has_sig!s:5} strong={has_strong!s:5} :: {p!r}")

out("\nNote: 'не учт'+'тестирован'+'функционал' alone (no verb) -> is_1c=False by design")
out("(is_1c requires JIRA | definitive | (signal|strong)+verb). T3 ttype only assigned AFTER is_1c.")
out("Question: do real T3 inputs from chat reliably carry a verb? Memory taxonomy says T3 =")
out("'дельта на прежнюю задачу' -- usually phrased as an action ('доработать/добавить/учесть').")

# Does 'учесть' / 'учитывать' (natural T3 verb) get caught?
out("\nNatural T3 verbs NOT in _TASK_VERB:")
for v in ["учесть", "учитывать", "не учли", "не хватает", "не работает", "должно", "ожидается"]:
    out(f"  _TASK_VERB.search({v!r:14}) = {bool(m._TASK_VERB.search(v))}")

sys.stdout.buffer.write(buf.getvalue().encode("utf-8"))
