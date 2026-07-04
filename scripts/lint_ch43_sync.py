#!/usr/bin/env python3
"""P3.5 (roadmap 260703): doc-drift линтер главы 43 «Пайплайн 1С».

Сверяет `docs/framework documentation/43_ПАЙПЛАЙН_1С/*.md` с РЕАЛЬНЫМ кодом по реестру
инвариантов — автоматизирует ручную верификацию, которая за сессию 260703 ловила дрейф
четырежды (subagent-редакторы вносили новый дрейф вместо устранения). Расширяемый:
новый инвариант = функция `(docs, code_facts) -> list[Finding]` в `INVARIANTS`.

Факты берутся ИЗ КОДА (import моста + ast + regex), не хардкодятся → линтер не устаревает
вместе с доками. Курируемые списки (фантомные тулы, known-bad формулировки) — единственное
исключение (их нельзя вывести из кода).

CLI:
  python scripts/lint_ch43_sync.py            # человекочитаемый отчёт, exit 0 (advisory)
  python scripts/lint_ch43_sync.py --json      # машинный JSON
  python scripts/lint_ch43_sync.py --strict    # exit 1 при находках (для CI-гейта)

CI-роль: advisory-джоб (не валит билд по умолчанию — доки живее кода; `--strict` при промоуте).
stdlib-only.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CH = ROOT / "docs" / "framework documentation" / "43_ПАЙПЛАЙН_1С"
BRIDGE = ROOT / ".claude" / "hooks" / "shared" / "pipeline_1c_bridge.py"
ONEC_STOP = ROOT / ".claude" / "hooks" / "onec-task-completion-stop.py"


@dataclass
class Finding:
    invariant: str
    file: str
    line: int
    detail: str
    severity: str  # high | med | low


# ─── Извлечение фактов из кода ───────────────────────────────────────────────────────────


def _load_module(path: Path, name: str):
    """Импорт hook-модуля по пути (standalone-скрипт контролирует sys.path → нет shared-коллизии)."""
    hooks = str(path.parent.parent) if path.parent.name == "shared" else str(path.parent)
    if hooks not in sys.path:
        sys.path.insert(0, hooks)
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def code_facts() -> dict:
    """Собрать факты из кода: flow-значения, группы весов effort, hard-ключи sig."""
    facts: dict = {"flow_values": set(), "effort_groups": set(), "errors": []}
    src = BRIDGE.read_text(encoding="utf-8")
    # flow-значения: (а) авторитетный enum из docstring `flow ∈ {none, ask_1c, …}`;
    # (б) литеральные присваивания `out["flow"] = "…"` / `"flow": "…"`.
    flows: set[str] = set(re.findall(r'"flow"\]\s*=\s*"(\w+)"', src)) | set(
        re.findall(r'"flow":\s*"(\w+)"', src)
    )
    m_enum = re.search(r"flow\s*∈\s*\{([^}]+)\}", src)
    if m_enum:
        flows |= {t.strip() for t in re.findall(r"\w+", m_enum.group(1))}
    facts["flow_values"] = flows
    # группы весов из _EFFORT_CFG["weights"] через ast (устойчиво к переформату)
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "_EFFORT_CFG" for t in node.targets
            ):
                for k, v in zip(node.value.keys, node.value.values):
                    if (
                        isinstance(k, ast.Constant)
                        and k.value == "weights"
                        and isinstance(v, ast.Dict)
                    ):
                        facts["effort_groups"] = {
                            kk.value for kk in v.keys if isinstance(kk, ast.Constant)
                        }
    except (SyntaxError, ValueError) as e:
        facts["errors"].append(f"ast _EFFORT_CFG: {e}")
    return facts


# ─── Курируемые списки (нельзя вывести из кода) ──────────────────────────────────────────

# Фантомные MCP-тулы: имена, которых НЕТ как MCP-инструментов. Флаг, если упомянуты БЕЗ
# рядом-стоящего квалификатора «не существует / обёртка / фантом».
_PHANTOM_TOOLS = ("bsl_replace_method_body", "bsl_safe_delete_symbol", "compare_semantic")
_PHANTOM_QUALIFIERS = (
    "не сущест",
    "не существ",
    "фантом",
    "обёртк",
    "обертк",
    "bsl-symbol-editing",
    "не экспон",
    "сервером не",
    "как mcp-тулы не",
)

# Формулировки, которые код опроверг (known-bad → дрейф). (bad_rx, пояснение, unless_rx):
# unless_rx — если совпал в той же строке, это КОРРЕКТИРУЮЩЕЕ упоминание («не «двухуровневый»»),
# не дрейф → пропустить.
_KNOWN_BAD = [
    (
        re.compile(r"двухуровнев", re.I),
        "детектор многоуровневый (JIRA→definitive→code→signal+verb→семантика→veto), не «двухуровневый»",
        re.compile(r"многоуровнев|не[\s«\"]+двухуровн", re.I),
    ),
    (
        re.compile(r"0 BLOCKER/CRITICAL на затронутых файл", re.I),
        "Sonar-гейт = mode=changed-lines (по изменённым СТРОКАМ), не «на затронутых файлах»",
        None,
    ),
    (
        re.compile(r"T3[–-]T4", re.I),
        "tier-таксономия кода = T1/T2 (ADR-035) + Тир-2 + T1 (ADR-036); «T3-T4» выдумана",
        None,
    ),
]

# Канонический flow-enum по коду (fallback, если regex-извлечение пусто). Проверяется против кода.
_CANON_FLOW = {"none", "ask_1c", "auto", "ask_flow", "ask_action", "gated"}


# ─── Инварианты ──────────────────────────────────────────────────────────────────────────


def inv_no_line_anchors(files: dict, facts: dict) -> list[Finding]:
    """Ссылки на живой код с `#L<номер>` — дрейфуют при каждой правке (P2.7 запретил)."""
    out = []
    rx = re.compile(r"[\w./-]+\.py#L\d+")
    for name, lines in files.items():
        for i, ln in enumerate(lines, 1):
            for m in rx.finditer(ln):
                out.append(
                    Finding("no-line-anchors", name, i, f"якорь на код: {m.group(0)}", "med")
                )
    return out


def inv_flow_enum(files: dict, facts: dict) -> list[Finding]:
    """Явно перечисленный flow-enum должен совпадать с набором значений кода (6)."""
    out = []
    code_flows = facts["flow_values"] or set(_CANON_FLOW)
    # ищем строки-«перечни» вида a/b/c/d/e из flow-токенов (≥4 подряд через / или запятую)
    tok = r"(?:none|ask_1c|ask_action|ask_flow|auto|gated)"
    listing = re.compile(rf"(?:{tok})(?:\s*[/,·|]\s*{tok}){{3,}}")
    for name, lines in files.items():
        for i, ln in enumerate(lines, 1):
            m = listing.search(ln)
            if not m:
                continue
            mentioned = set(re.findall(tok, m.group(0)))
            missing = code_flows - mentioned
            if missing:
                out.append(
                    Finding(
                        "flow-enum",
                        name,
                        i,
                        f"перечень flow неполон: нет {sorted(missing)} (код: {sorted(code_flows)})",
                        "med",
                    )
                )
    return out


def inv_effort_groups(files: dict, facts: dict) -> list[Finding]:
    """Таблица весов estimate_effort должна упоминать все группы `_EFFORT_CFG['weights']`."""
    groups = facts["effort_groups"]
    if not groups:
        return []
    # ttype_T1/ttype_T3 в доках часто как «ttype» — нормализуем
    doc_terms = {g.split("_")[0] if g.startswith("ttype") else g for g in groups}
    joined = "\n".join("\n".join(v) for v in files.values())
    missing = sorted(t for t in doc_terms if t not in joined)
    # проверяем только в 43.3/43.5.5 (где таблица весов); если группа не упомянута НИГДЕ в главе
    if missing:
        return [
            Finding(
                "effort-groups",
                "(вся глава)",
                0,
                f"группы весов _EFFORT_CFG не упомянуты в главе: {missing}",
                "low",
            )
        ]
    return []


def inv_phantom_tools(files: dict, facts: dict) -> list[Finding]:
    """Фантомные MCP-тулы упомянуты как рекомендация без квалификатора «не существует»."""
    out = []
    for name, lines in files.items():
        for i, ln in enumerate(lines, 1):
            low = ln.lower()
            for ph in _PHANTOM_TOOLS:
                if ph.lower() in low and not any(q in low for q in _PHANTOM_QUALIFIERS):
                    out.append(
                        Finding(
                            "phantom-tools", name, i, f"фантомный тул без оговорки: {ph}", "high"
                        )
                    )
    return out


def inv_known_bad(files: dict, facts: dict) -> list[Finding]:
    """Формулировки, которые код опроверг (устранённый дрейф не должен вернуться)."""
    out = []
    for name, lines in files.items():
        for i, ln in enumerate(lines, 1):
            for rx, why, unless in _KNOWN_BAD:
                if rx.search(ln) and not (unless and unless.search(ln)):
                    out.append(Finding("known-bad", name, i, why, "med"))
    return out


INVARIANTS = [
    inv_no_line_anchors,
    inv_flow_enum,
    inv_effort_groups,
    inv_phantom_tools,
    inv_known_bad,
]


# ─── Runner ──────────────────────────────────────────────────────────────────────────────


def run() -> list[Finding]:
    files = {p.name: p.read_text(encoding="utf-8").splitlines() for p in sorted(CH.glob("*.md"))}
    facts = code_facts()
    findings: list[Finding] = []
    for inv in INVARIANTS:
        try:
            findings.extend(inv(files, facts))
        except Exception as e:  # инвариант не должен ронять линтер
            findings.append(Finding(inv.__name__, "(linter)", 0, f"ошибка инварианта: {e}", "low"))
    return findings


def main() -> int:
    ap = argparse.ArgumentParser(description="doc-drift линтер главы 43 (P3.5)")
    ap.add_argument("--json", action="store_true", help="машинный JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 при находках (CI-гейт)")
    args = ap.parse_args()
    try:  # Windows cp1251-консоль не кодирует кириллицу → форсим UTF-8 (CI Linux уже UTF-8)
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    findings = run()
    if args.json:
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    else:
        if not findings:
            print("[lint-ch43] CLEAN — дрейф не обнаружен по реестру инвариантов")
        else:
            by_sev = {"high": [], "med": [], "low": []}
            for f in findings:
                by_sev.setdefault(f.severity, []).append(f)
            print(f"[lint-ch43] {len(findings)} находок ({len(by_sev['high'])} high):")
            for sev in ("high", "med", "low"):
                for f in by_sev[sev]:
                    loc = f"{f.file}:{f.line}" if f.line else f.file
                    print(f"  [{sev}] {f.invariant} — {loc}: {f.detail}")
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
