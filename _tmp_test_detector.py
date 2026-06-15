# -*- coding: utf-8 -*-
"""Empirical review of classify_1c_task / route_1c_task. Imports the REAL module."""
import os
import re
import sys
import time

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".claude", "hooks")
sys.path.insert(0, HOOKS)
from shared import pipeline_1c_bridge as m  # noqa: E402

S = m._1C_STRONG
SIG = m._1C_SIGNAL
DEF = m._1C_DEFINITIVE

print("=" * 60)
print("TEST 1: re.I on CamelCase regex?")
print("=" * 60)
print("  _1C_STRONG has IGNORECASE:", bool(S.flags & re.IGNORECASE))
print("  _1C_STRONG has UNICODE   :", bool(S.flags & re.UNICODE))
print("  _1C_SIGNAL has IGNORECASE :", bool(SIG.flags & re.IGNORECASE))

print("\n-- hump semantics: real CamelCase MUST match --")
for s in ["ПриЗаписи", "ТабличныйДокумент", "НаправлениеНаРазгрузку"]:
    print(f"  {s!r:40} -> {bool(S.search(s))}")

print("\n-- NON-CamelCase MUST NOT match via the CamelCase class --")
# strip other alternatives by testing plain Cyrillic words w/o дот/гкс_
for s in ["привет мир", "ПРИВЕТ ВСЕМ", "просто обычный текст", "все строчные слова"]:
    print(f"  {s!r:40} -> {bool(S.search(s))}")

print("\n-- counterfactual: if re.I were set, ANY 3 cyr would match --")
strong_I = re.compile(r"[а-яё][А-ЯЁ][а-яё]", re.I | re.U)
print("  re.I-version on 'привет':", bool(strong_I.search("привет")), "(would be over-match)")
print("  re.U-only on 'привет'   :", bool(re.compile(r"[а-яё][А-ЯЁ][а-яё]", re.U).search("привет")))

print("\n" + "=" * 60)
print("TEST 3: \\b word boundary on Cyrillic")
print("=" * 60)
cases = [
    ("информация", False, "форм inside, \\bформ[аеуы] must NOT match"),
    ("информацию", False, "форм inside"),
    ("форма", True, "\\bформ[аеуы] matches"),
    ("эта форма", True, "word-start"),
    ("переформатировать", False, "форм mid-word"),
    ("документация", True, "STARTS with документ -> \\bдокумент matches prefix"),
    ("задокументировать", False, "документ mid-word"),
    ("этот документ", True, "word-start"),
    ("реквизиты", True, "реквизит no \\b -> substring ok"),
    ("аэропорт", False, "no signal"),
]
for s, expect, why in cases:
    got = bool(SIG.search(s))
    flag = "OK " if got == expect else "!! MISMATCH"
    print(f"  [{flag}] {s!r:22} got={got} expect={expect}  ({why})")

print("\n" + "=" * 60)
print("TEST 2: ReDoS / catastrophic backtracking")
print("=" * 60)
pathological = [
    ("Регистр*5000", "Регистр" * 5000),
    ("План*5000", "План" * 5000),
    ("(аааБ)*5000", ("ааа" + "Б") * 5000),
    ("Регистр+Я*100000", "Регистр" + "Я" * 100000),
    ("x*500000", "x" * 500000),
    ("аА*200000", ("аА") * 200000),
]
for label, t in pathological:
    t0 = time.perf_counter()
    S.search(t)
    SIG.search(t)
    DEF.search(t)
    dt = (time.perf_counter() - t0) * 1000
    print(f"  {label:22} len={len(t):>7}: {dt:8.2f} ms")
