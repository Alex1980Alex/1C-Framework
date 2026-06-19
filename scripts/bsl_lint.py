#!/usr/bin/env python3
"""bsl_lint.py — диагностики BSL по запросу через bundled bsl-language-server.jar.

Реализация ADR-020 «своя обвязка над bundled bsl-ls» — inline BSL-LSP диагностики
БЕЗ внешнего плагина/Docker (claude-code-bsl-lsp SKIP, mcp-bsl-lsp-bridge EVAL).
Запускает BSL Language Server в режиме `--analyze` и отдаёт диагностики (JSON или
человекочитаемо). Точнее, чем OneScript-линтер `bsl_analyze` (128+ диагностик vs
парсер-парсинг), и не требует EDT round-trip. Reusable ядро для будущего хука/MCP.

Java ищется в порядке: $JAVA_HOME → 1C:EDT Axiom JDK 17 → bundled sonar JRE → PATH.
(Bundled `tools/*/jre/bin/java.exe` — Git-LFS exe, часто НЕ выгружен в dev-чекауте;
`.jar`-ы выгружены. См. ADR-020 + кеш 1c-bsl-tooling-ecosystem-2026.md.)

Usage:
  # Диагностика:
  .venv/Scripts/python.exe scripts/bsl_lint.py <файл.bsl | каталог> [--json]
        [--config <.bsl-language-server.json>] [--severity error|warning|info]
        [--fail-on-error] [--java <path>]
  # Форматирование (правит файлы in-place через bsl-ls `--format`):
  .venv/Scripts/python.exe scripts/bsl_lint.py <файл.bsl | каталог> --format [--config <...>]

Exit: 0 (по умолчанию, advisory). С `--fail-on-error` → 1 при наличии диагностик severity=Error.
Технические сбои (нет Java / нет jar / LS не отработал) → 2.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BSL_LS_JAR = PROJECT_ROOT / "tools" / "bsl-ls" / "bsl-language-server.jar"
_MIN_REAL_BYTES = 1000  # Git-LFS pointer ~130 байт; реальный бинарь сильно больше
_EXE = "java.exe" if os.name == "nt" else "java"
# bsl-ls severity (LSP DiagnosticSeverity): 1=Error 2=Warning 3=Information 4=Hint
_SEV_NAME = {1: "error", 2: "warning", 3: "info", 4: "hint"}
_SEV_MIN = {"error": 1, "warning": 2, "info": 3, "hint": 4}


def _runnable(p: str | os.PathLike) -> bool:
    try:
        return Path(p).is_file() and Path(p).stat().st_size > _MIN_REAL_BYTES
    except OSError:
        return False


def find_java(explicit: str | None = None) -> str | None:
    """Найти запускаемый java. Пропускает LFS-указатели (<1KB)."""
    if explicit:
        return explicit if _runnable(explicit) else None
    jh = os.environ.get("JAVA_HOME")
    if jh and _runnable(Path(jh) / "bin" / _EXE):
        return str(Path(jh) / "bin" / _EXE)
    # 1C:EDT Axiom JDK 17 (bsl-ls 0.22 требует JDK 17)
    edt_globs = [
        r"C:\Program Files\1C\1CE\components\axiom-jdk*\bin\java.exe",
        r"C:\Program Files\1cedt\**\jre\bin\java.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\1C_EDT\**\jre\bin\java.exe"),
    ]
    for pat in edt_globs:
        for hit in glob.glob(pat, recursive=True):
            if _runnable(hit):
                return hit
    # bundled sonar JRE (если LFS выгружен)
    for hit in glob.glob(str(PROJECT_ROOT / "tools" / "sonar-scanner-*" / "jre" / "bin" / _EXE)):
        if _runnable(hit):
            return hit
    # PATH
    onpath = shutil.which("java")
    return onpath if onpath else None


def _code_str(code) -> str:
    if isinstance(code, dict):
        return str(code.get("value") or code.get("target") or code)
    return str(code) if code is not None else ""


def run_analyze(java: str, src_dir: Path, config: Path, out_dir: Path) -> tuple[int, str]:
    cmd = [
        java,
        "-jar",
        str(BSL_LS_JAR),
        "--analyze",
        "--srcDir",
        str(src_dir),
        "--reporter",
        "json",
        "--outputDir",
        str(out_dir),
        "--configuration",
        str(config),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600)
    return proc.returncode, (proc.stderr or "") + (proc.stdout or "")


def run_format(java: str, src_dir: Path, config: Path) -> tuple[int, str]:
    """Запустить bsl-ls в режиме форматирования (правит .bsl/.os in-place в src_dir).

    bsl-ls CLI: `format, -f, --format` (подтверждён `--help`). Принимает --srcDir и
    --configuration. rc=0 при успехе; файлы переписываются на месте.
    """
    cmd = [
        java,
        "-jar",
        str(BSL_LS_JAR),
        "--format",
        "--srcDir",
        str(src_dir),
        "--configuration",
        str(config),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=600)
    return proc.returncode, (proc.stderr or "") + (proc.stdout or "")


def _do_format(java: str, target: Path, config_arg: str | None) -> int:
    """Отформатировать файл/каталог. Для одиночного файла — write-back ТОЛЬКО при
    реальном изменении (точные байты → сохраняется BOM/кодировка 1С). Каталог — in-place.
    Advisory: возвращает 0; при rc!=0 от bsl-ls печатает предупреждение в stderr.
    """
    with tempfile.TemporaryDirectory(prefix="bsl_fmt_") as td:
        tdp = Path(td)
        if config_arg:
            config = Path(config_arg)
        else:
            config = tdp / ".bsl-language-server.json"
            config.write_text(json.dumps({"language": "ru"}), encoding="utf-8")
        if target.is_file():
            src_dir = tdp / "src"
            src_dir.mkdir()
            tmp_file = src_dir / target.name
            shutil.copy(target, tmp_file)
            before = target.read_bytes()
            rc, log = run_format(java, src_dir, config)
            if (
                not tmp_file.exists()
            ):  # bsl-ls не вернул файл → не трактуем как «без изменений» молча
                print(
                    f"[bsl_lint] предупреждение: bsl-ls не вернул файл во временный srcDir "
                    f"(rc={rc}) — оригинал не тронут",
                    file=sys.stderr,
                )
                after = before
            else:
                after = tmp_file.read_bytes()
            if after != before and rc == 0:
                target.write_bytes(after)
                print(f"[bsl_lint] {target.name}: отформатирован ✓ (изменён)")
            elif (
                after != before
            ):  # есть отличия, но rc!=0 → не доверяем выводу, оригинал НЕ перезаписан
                print(
                    f"[bsl_lint] {target.name}: НЕ перезаписан (bsl-ls format rc={rc}); см. stderr"
                )
            else:
                print(f"[bsl_lint] {target.name}: уже отформатирован ✓ (без изменений)")
        else:
            rc, log = run_format(java, target, config)
            print(f"[bsl_lint] {target}: прогон форматирования завершён (rc={rc})")
        if rc != 0:
            print(f"[bsl_lint] предупреждение: bsl-ls format rc={rc}\n{log[:800]}", file=sys.stderr)
    return 0


def parse_report(report: Path) -> list[dict]:
    """Распарсить bsl-language-server-report.json (reporter=json) в плоский список."""
    data = json.loads(report.read_text(encoding="utf-8"))
    out: list[dict] = []
    for fi in data.get("fileinfos", []):
        path = fi.get("path", "")
        for d in fi.get("diagnostics", []):
            start = (d.get("range") or {}).get("start") or {}
            sev = d.get("severity")
            # bsl-ls JSON: severity = строка ("Error"/"Warning"/"Information"/"Hint"), не LSP-int.
            # Нормализуем к lowercase (+ Information→info), с поддержкой int на случай др. версий.
            if isinstance(sev, int):
                sev_name = _SEV_NAME.get(sev, str(sev))
            else:
                _s = str(sev or "").strip().lower()
                sev_name = {"information": "info", "informational": "info"}.get(_s, _s)
            out.append(
                {
                    "file": path,
                    "line": (start.get("line", -1) + 1)
                    if isinstance(start.get("line"), int)
                    else None,
                    "column": (start.get("character", -1) + 1)
                    if isinstance(start.get("character"), int)
                    else None,
                    "severity": sev_name,
                    "code": _code_str(d.get("code")),
                    "message": d.get("message", ""),
                }
            )
    return out


def main(argv: list[str] | None = None) -> int:
    for _stream in (sys.stdout, sys.stderr):  # cp1251-консоль: кириллица в диагностиках И ошибках
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(
        prog="bsl_lint", description="BSL diagnostics via bundled bsl-language-server"
    )
    ap.add_argument("path", help="файл .bsl/.os или каталог")
    ap.add_argument("--json", action="store_true", help="вывод JSON-списком")
    ap.add_argument(
        "--config", default=None, help="путь к .bsl-language-server.json (по умолч. {language:ru})"
    )
    ap.add_argument(
        "--severity", choices=list(_SEV_MIN), default=None, help="минимальный уровень для вывода"
    )
    ap.add_argument("--fail-on-error", action="store_true", help="exit 1 при severity=error")
    ap.add_argument(
        "--format",
        action="store_true",
        help="режим форматирования: переписать файл(ы) через bsl-ls (in-place), вместо диагностики",
    )
    ap.add_argument("--java", default=None, help="явный путь к java")
    args = ap.parse_args(argv)

    java = find_java(args.java)
    if not java:
        print(
            "[bsl_lint] ОШИБКА: не найден запускаемый java (JAVA_HOME / 1C:EDT Axiom JDK / bundled JRE / PATH). "
            "Bundled JRE — Git-LFS exe, возможно не выгружен (`git lfs pull`).",
            file=sys.stderr,
        )
        return 2
    if not _runnable(BSL_LS_JAR):
        print(
            f"[bsl_lint] ОШИБКА: нет {BSL_LS_JAR} (или это LFS-указатель). `git lfs pull`.",
            file=sys.stderr,
        )
        return 2

    target = Path(args.path)
    if not target.exists():
        print(f"[bsl_lint] ОШИБКА: путь не найден: {target}", file=sys.stderr)
        return 2

    if args.format:  # режим форматирования (правит файлы), не диагностика
        return _do_format(java, target, args.config)

    with tempfile.TemporaryDirectory(prefix="bsl_lint_") as td:
        tdp = Path(td)
        if target.is_file():
            src_dir = tdp / "src"
            src_dir.mkdir()
            shutil.copy(target, src_dir / target.name)
        else:
            src_dir = target
        if args.config:
            config = Path(args.config)
        else:
            config = tdp / ".bsl-language-server.json"
            config.write_text(json.dumps({"language": "ru"}), encoding="utf-8")
        out_dir = tdp / "out"
        out_dir.mkdir()

        rc, log = run_analyze(java, src_dir, config, out_dir)
        # reporter=json пишет `bsl-json.json` (0.22); имя варьируется по версиям → glob + предпочесть известные
        reports = sorted(out_dir.rglob("*.json"))
        report = next(
            (r for r in reports if r.name in ("bsl-json.json", "bsl-language-server-report.json")),
            reports[0] if reports else None,
        )
        if report is None:
            print(
                f"[bsl_lint] ОШИБКА: bsl-ls не создал отчёт (rc={rc}).\n{log[:2000]}",
                file=sys.stderr,
            )
            return 2
        diags = parse_report(report)
        if target.is_file():  # вернуть исходный путь вместо temp-копии
            for d in diags:
                d["file"] = str(target)

    if args.severity:
        thr = _SEV_MIN[args.severity]
        diags = [d for d in diags if _SEV_MIN.get(d["severity"], 9) <= thr]

    if args.json:
        print(json.dumps(diags, ensure_ascii=False, indent=2))
    else:
        if not diags:
            print(f"[bsl_lint] {target.name}: диагностик нет ✓")
        else:
            print(f"[bsl_lint] {target.name}: {len(diags)} диагностик(и):")
            for d in diags:
                loc = f"{Path(d['file']).name}:{d['line']}" if d["line"] else Path(d["file"]).name
                print(f"  [{d['severity']}] {loc}  {d['code']}: {d['message']}")

    if args.fail_on_error and any(d["severity"] == "error" for d in diags):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
