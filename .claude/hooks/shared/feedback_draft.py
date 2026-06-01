"""
Shared: detect code-review feedback in a user prompt and create a DRAFT
curated-memory candidate (Variant A, draft-mode).

Goal: when the user gives a reusable code-review rule ("use X instead of Y",
"читай через БСП, не разыменование"), auto-create a *draft* under
data/memory_drafts/ so the assistant/user can confirm it into curated memory
(memory/feedback_*.md + MEMORY.md). Drafts are NOT written to curated memory
automatically — confirmation stays manual (no pollution without review).

Fail-soft: every function swallows errors and returns a safe value.
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path

# .../.claude/hooks/shared/feedback_draft.py -> parents[3] == project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
DRAFTS_DIR = _PROJECT_ROOT / "data" / "memory_drafts"

# Correction / reusable-rule phrases (RU + EN). Liberal recall; precision comes
# from the additional _CODE_TOKEN requirement + draft-mode confirmation.
_RULE_PATTERNS = [
    r"вместо\s+\S+.{0,40}?(использ|должн|нужно|примен|сдела)",
    r"использ\w*\b.{0,40}?\bвместо\b",
    r"должн[аоы]\b.{0,40}?(по\s+умолчанию|заполн|брат|использ)",
    r"использ\w*\s+(функци|метод|бсп|общегоназначения|обработкаошибок)",
    r"замен\w+\b.{0,40}?\bна\b",
    r"\bне\s+(делай|читай|использ\w*|пиши|обращайся)\b",
    r"\bвсегда\b.{0,40}?(использ|примен|делай)",
    r"use\s+\w+.{0,40}?instead\s+of",
    r"do\s*n['`]?t\s+use\b",
    r"\bprefer\b\s+\w+",
]
_RULE_RE = [re.compile(p, re.IGNORECASE) for p in _RULE_PATTERNS]

# A code-ish token in the prompt (dotted call / backticked code / 1C keywords)
# strongly raises the odds this is an actionable code rule, not chit-chat.
_CODE_TOKEN = re.compile(
    r"[A-Za-zА-Яа-яЁё_]\w*\.[A-Za-zА-Яа-яЁё_]\w*"
    r"|`[^`]+`"
    r"|функци|метод|реквизит|модул|процедур|запрос|ссылк"
    r"|БСП|ОбщегоНазначения|ОбработкаОшибок",
    re.IGNORECASE,
)


def detect_feedback(prompt):
    """Return the matched rule-pattern string if the prompt looks like a
    reusable code-review rule, else None."""
    try:
        if not prompt or len(prompt) < 12:
            return None
        if not _CODE_TOKEN.search(prompt):
            return None
        for rx in _RULE_RE:
            if rx.search(prompt):
                return rx.pattern
        return None
    except Exception:
        return None


def _draft_key(prompt):
    norm = re.sub(r"\s+", " ", str(prompt).strip().lower())[:300]
    return hashlib.sha1(norm.encode("utf-8", errors="replace")).hexdigest()[:12]


_DRAFT_TEMPLATE = """---
name: feedback-draft-{key}
description: "<ЧЕРНОВИК: уточнить правило одной строкой при подтверждении>"
metadata:
  type: feedback
  status: pending
  source: feedback-detector
  session: {session}
  created: {created}
---

> ЧЕРНОВИК курируемой памяти (авто-детект код-ревью замечания). Подтвердить =
> уточнить правило ниже и перенести в
> projects/C--1--Framework/memory/feedback_<slug>.md + строка в MEMORY.md.
> Неактуально = удалить этот файл.

**Исходное замечание пользователя:**
{excerpt}

**Правило (заполнить при подтверждении):** <что делать / чего НЕ делать>
**Why:** <причина>
**How to apply:** <когда применять>
"""


def create_draft(prompt, session_id=""):
    """Create a pending draft candidate. Returns path str, or None on
    dedupe-hit / error. Never raises."""
    try:
        DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
        key = _draft_key(prompt)
        for existing in DRAFTS_DIR.glob("*.md"):
            if key in existing.name:
                return None  # dedupe: same normalized feedback already drafted
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DRAFTS_DIR / ("{0}_{1}.md".format(ts, key))
        excerpt = str(prompt).replace("\r", "").strip()
        if len(excerpt) > 800:
            excerpt = excerpt[:800] + " …"
        content = _DRAFT_TEMPLATE.format(
            key=key,
            session=session_id or "—",
            created=datetime.now().isoformat(timespec="seconds"),
            excerpt=excerpt,
        )
        path.write_text(content, encoding="utf-8")
        return str(path)
    except Exception:
        return None


def list_pending_drafts():
    """Return sorted list of pending draft Paths (oldest first). Never raises."""
    try:
        if not DRAFTS_DIR.exists():
            return []
        return sorted(DRAFTS_DIR.glob("*.md"))
    except Exception:
        return []