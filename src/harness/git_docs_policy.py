"""Pure cochange rules extracted from the Codex docs policy on 15.11.2026."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_RAW = Path(__file__).with_name("git_docs_rules.json").read_bytes()
RULES = json.loads(_RAW.decode("utf-8"))
POLICY_VERSION = "git-docs-v1"
POLICY_SHA256 = hashlib.sha256(_RAW).hexdigest()
_DOCS_BASE = RULES["DOCS_BASE"]
_CODE_TO_DOMAIN = RULES["CODE_TO_DOMAIN"]
_SKIP_PATTERNS = tuple(p.lower() for p in RULES["SKIP_PATTERNS"])
_INFRA_DOC = (_DOCS_BASE + "/7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/"
              "09.7_Система_хуков.md")


def _is_infra(lower):
    if lower in {".claude/settings.json", ".codex/hooks.json"}:
        return True
    if lower.endswith(".py") and lower.startswith((".claude/hooks/", ".codex/hooks/")):
        return True
    return (lower.startswith((".claude/skills/", ".agents/skills/"))
            and not lower.endswith("/skill.md"))


def _domain_updated(updated_lower, domain, skill):
    prefixes = ((_DOCS_BASE + "/" + domain + "/").lower(),
                f".claude/skills/{skill}/".lower(), f".agents/skills/{skill}/".lower())
    return any(p.startswith(prefixes) for p in updated_lower)


def evaluate(paths, updated):
    """Check explicit paths; updated contains changed, nonempty regular Git blobs."""
    updated_lower = frozenset(p.lower() for p in updated)
    findings = []
    for original in sorted(set(paths)):
        lower = original.lower()
        if any(pattern in lower for pattern in _SKIP_PATTERNS):
            continue
        if _is_infra(lower):
            if not updated_lower.intersection({"claude.md", _INFRA_DOC.lower()}):
                findings.append({"file": original, "rule": "infra-docs",
                                 "required": _INFRA_DOC.lower()})
            continue
        for prefix, domain, skill in _CODE_TO_DOMAIN:
            if lower.startswith(prefix.lower()):
                if domain is not None and not _domain_updated(updated_lower, domain, skill):
                    findings.append({"file": original, "rule": "domain-docs",
                                     "required": (_DOCS_BASE + "/" + domain + "/").lower()})
                break
        else:
            findings.append({"file": original, "rule": "unmapped", "required": "audit-docs"})
    return findings
