#!/usr/bin/env python3
"""
BSL Tool Router — направляет BSL-задачи к правильным MCP tools.

Phase 44: Infrastructure migration from 1C-Enterprise_Framework
"""

import sys
import json


def main() -> None:
    """Main hook entry point."""
    try:
        raw = sys.stdin.buffer.read().decode("utf-8")
        hook_input = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        # If we can't parse input, just approve
        print(json.dumps({"decision": "approve"}))
        return

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Detect BSL file work
    bsl_signals = []

    file_path = tool_input.get("file_path", "") or tool_input.get("path", "")
    if file_path and file_path.endswith(".bsl"):
        bsl_signals.append("BSL file detected")

    # Check for BSL-related commands
    command = tool_input.get("command", "")
    if isinstance(command, str):
        bsl_keywords = [".bsl", "1c-enterprise", "bsl-semantic", "1с", "справочник", "документ"]
        if any(kw in command.lower() for kw in bsl_keywords):
            bsl_signals.append("BSL command detected")

    # Check for BSL-related patterns
    pattern = tool_input.get("pattern", "")
    if isinstance(pattern, str):
        bsl_patterns = ["Процедура", "Функция", "КонецПроцедуры", "КонецФункции"]
        if any(p in pattern for p in bsl_patterns):
            bsl_signals.append("BSL pattern detected")

    result = {"decision": "approve"}

    if bsl_signals:
        # Determine recommended reasoner strategy based on context
        context_text = (file_path + " " + command + " " + pattern).lower()
        strategy_hint = "bsl_architecture"
        if any(w in context_text for w in ["проведен", "движен", "регистр", "документ", "posting"]):
            strategy_hint = "bsl_document_patterns"
        elif any(w in context_text for w in ["подсистем", "rbac", "rls", "интеграц", "зависимост"]):
            strategy_hint = "bsl_subsystem_analysis"

        result["message"] = (
            f"[BSL-ROUTER] {', '.join(bsl_signals)}. "
            f"ОБЯЗАТЕЛЬНО: mcp__reasoner (strategyType='{strategy_hint}'), "
            "mcp__bsl-semantic-search (поиск кода), "
            "mcp__auto-documenter (документация), "
            "mcp__bsl-debugger (отладка), "
            "mcp__bsl-platform-context (API 1С), "
            "mcp__serena (LSP/символы), "
            "mcp__ast-grep-mcp (AST анализ)"
        )

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
