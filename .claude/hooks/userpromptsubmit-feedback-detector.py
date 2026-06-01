#!/usr/bin/env python3
"""
Hook: userpromptsubmit-feedback-detector
Event: UserPromptSubmit
Matcher: (none)
Purpose: Detect a reusable code-review rule in the user prompt ("use X instead
         of Y", "читай через БСП, не разыменование") and create a DRAFT curated
         memory candidate in data/memory_drafts/ (draft-mode — not written to
         curated memory automatically). Emits a suggestion to confirm.
         Closes the gap where code-review feedback never reaches curated memory.
Opt-out: FEEDBACK_DRAFT_DISABLE=1
Timeout: 3s
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput
from shared.feedback_draft import create_draft, detect_feedback


class FeedbackDetector(BaseHook):

    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "UserPromptSubmit":
            return None
        if os.environ.get("FEEDBACK_DRAFT_DISABLE") == "1":
            return None

        prompt = inp.prompt or ""
        if not detect_feedback(prompt):
            return None

        path = create_draft(prompt, inp.session_id)
        if not path:
            return None  # dedupe-hit or write error — stay silent

        name = os.path.basename(path)
        return HookOutput().system_message(
            "[FEEDBACK-DRAFT] Похоже на переиспользуемое код-ревью правило.\n"
            "Создан ЧЕРНОВИК курируемой памяти: data/memory_drafts/" + name + "\n"
            "Если это правило — уточни его и перенеси в memory/feedback_<slug>.md + строку в MEMORY.md "
            "(подтверждение). Если нет — удали черновик. Отключить детектор: FEEDBACK_DRAFT_DISABLE=1."
        )


if __name__ == "__main__":
    FeedbackDetector().run()