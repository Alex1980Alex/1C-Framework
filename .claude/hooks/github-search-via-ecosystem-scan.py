#!/usr/bin/env python3
"""
Hook: github-search-via-ecosystem-scan
Event: PreToolUse
Matcher: WebSearch
Purpose: GitHub-поиск ОБЯЗАН идти через ecosystem_scan (ADR-039, гл.44), не через WebSearch.
         Блокирует WebSearch с GitHub-repo-discovery интентом → требует ecosystem_scan.
Timeout: 3s
Pattern: Enforcer (PreToolUse block). Opt-out: GITHUB_ECOSYSTEM_SCAN_DISABLE=1
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# Discovery-интент (repo/lib поиск) — чтобы не блокировать github-how-to вопросы
_DISCOVERY = re.compile(
    r"(stars?\s*[:>]|awesome|best[\s-]?practice|repos?\b|repositor|"
    r"librar|библиотек|framework|implementation|реализаци|\btools?\b)",
    re.I,
)


class GithubSearchGuard(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("GITHUB_ECOSYSTEM_SCAN_DISABLE") == "1":
            return None
        if inp.detected_event != "PreToolUse" or (inp.tool_name or "") != "WebSearch":
            return None

        ti = inp.tool_input or {}
        query = str(ti.get("query") or "")
        domains = ti.get("allowed_domains") or []
        ql = query.lower()

        explicit = (
            any("github.com" in str(d).lower() for d in domains)
            or "site:github.com" in ql
            or "github.com" in ql
        )
        worded = ("github" in ql or "гитхаб" in ql) and bool(_DISCOVERY.search(query))

        if not (explicit or worded):
            return None

        safe_q = re.sub(r'["\n\r]', " ", query)[:80]
        return HookOutput().block(
            "[GITHUB->ECOSYSTEM_SCAN] GitHub-поиск ОБЯЗАТЕЛЕН через ecosystem_scan (ADR-039, гл.44), не WebSearch.\n\n"
            f'Запусти: python scripts/ecosystem_scan.py "{safe_q}" --top 8\n'
            "Сканит GitHub/HN/SO/Lobsters/Dev.to с engagement x relevance ранжированием "
            "(docs/framework documentation/44_ECOSYSTEM_SCAN).\n"
            "1С/RU-веб -> onec_search (гл.44.6). Не-GitHub WebSearch не затронут.\n"
            "opt-out: GITHUB_ECOSYSTEM_SCAN_DISABLE=1"
        )


if __name__ == "__main__":
    GithubSearchGuard().run()
