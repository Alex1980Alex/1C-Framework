#!/usr/bin/env python3
"""
Hook: stop-feedback-draft-aggregator
Event: Stop
Matcher: (none)
Purpose: On session stop, remind about pending curated-memory drafts created by
         userpromptsubmit-feedback-detector (batch, cap 5). Non-blocking — never
         exits 2. Lets the assistant/user confirm or discard drafts at end of work.
Opt-out: FEEDBACK_DRAFT_DISABLE=1
Timeout: 3s
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.feedback_draft import list_pending_drafts


class FeedbackDraftAggregator(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "Stop":
            return None
        if os.environ.get("FEEDBACK_DRAFT_DISABLE") == "1":
            return None

        drafts = list_pending_drafts()
        if not drafts:
            return None

        shown = drafts[:5]
        lines = ["- data/memory_drafts/" + os.path.basename(str(p)) for p in shown]
        extra = "" if len(drafts) <= 5 else f"\n…и ещё {len(drafts) - 5}"
        return HookOutput().system_message(
            f"[FEEDBACK-DRAFT] Черновики курируемой памяти на подтверждение ({len(drafts)}):\n"
            + "\n".join(lines) + extra + "\n"
            "Подтверждённые перенеси в memory/feedback_*.md + MEMORY.md; неактуальные удали из data/memory_drafts/."
        )


if __name__ == "__main__":
    FeedbackDraftAggregator().run()
