#!/usr/bin/env python3
"""
Code Skill Enforcer — Skill-First Enforcement Hook

Event: PreToolUse | PostToolUse
Matcher: Write|Edit|Bash (PRE), Write|Edit|WebSearch|WebFetch (POST)
Purpose: Enforce skill usage before/after code operations
Timeout: 3s

Principle:
  PRE (before)  -> Check skill cache -> BLOCK if missing -> ACTIVATE -> retry
  POST (after)  -> Verify vs skill -> advisory messages

Levels:
  A: Content patterns (StateGraph -> langgraph-core)
  B: Directory rules (.claude/hooks/ -> create-hook)
  C: Bash commands (docker compose -> deployment)
  D: Research cache reminder (WebSearch -> check cache)
  E: Post-verification (must_contain, must_not_contain checks)
  F: LEARN phase (advisory backup for learning-loop)

Author: Claude Code
Version: 2.1.0
Created: 2026-02-23
Updated: 2026-03-03 (Level A.1: BLOCKING research_protocol → Skill('learning-loop'); Level F: advisory backup)
"""

import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

# Path resolution (same pattern as all other hooks)
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# Optional imports (graceful degradation)
try:
    from shared.session_state import SessionState
except ImportError:
    SessionState = None

try:
    from shared.task_master import add_task, has_recent_completion
except ImportError:
    add_task = None
    has_recent_completion = None


# ============================================================================
# Configuration Loader (lazy-load with caching)
# ============================================================================

class PatternConfig:
    """Lazy-loaded pattern configuration with caching."""

    _instance = None
    _config = None
    _compiled_patterns = {}

    CONFIG_PATH = os.path.join(_HOOK_DIR, "shared", "code-skill-patterns.json")

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self._config is None:
            self._load_config()

    def _load_config(self):
        self._config = {
            "patterns": {"mappings": []},
            "directory_rules": {"mappings": []},
            "bash_rules": {"mappings": []},
            "research_protocol": {"patterns": []},
            "post_verification": {"rules": []}
        }
        try:
            if os.path.exists(self.CONFIG_PATH):
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    self._config.update(json.load(f))
        except (json.JSONDecodeError, IOError):
            pass
        self._compile_patterns()

    def _compile_patterns(self):
        for section, key_prefix in [
            ("patterns", "pattern_"),
            ("bash_rules", "bash_"),
            ("research_protocol", "research_"),
        ]:
            items = self._config.get(section, {})
            item_list = items.get("mappings", []) or items.get("patterns", [])
            for item in item_list:
                pattern = item.get("pattern", "")
                key = f"{key_prefix}{pattern[:30]}"
                try:
                    self._compiled_patterns[key] = re.compile(pattern, re.IGNORECASE)
                except re.error:
                    pass

    def get_patterns(self):
        return self._config.get("patterns", {}).get("mappings", [])

    def get_directory_rules(self):
        return self._config.get("directory_rules", {}).get("mappings", [])

    def get_bash_rules(self):
        return self._config.get("bash_rules", {}).get("mappings", [])

    def get_research_protocol(self):
        return self._config.get("research_protocol", {}).get("patterns", [])

    def get_post_verification(self):
        return self._config.get("post_verification", {}).get("rules", [])

    def match_pattern(self, content):
        for mapping in self.get_patterns():
            pattern = mapping.get("pattern", "")
            key = f"pattern_{pattern[:30]}"
            compiled = self._compiled_patterns.get(key)
            if compiled and compiled.search(content):
                return mapping
        return None

    def match_bash(self, command):
        for mapping in self.get_bash_rules():
            pattern = mapping.get("pattern", "")
            key = f"bash_{pattern[:30]}"
            compiled = self._compiled_patterns.get(key)
            if compiled and compiled.search(command):
                return mapping
        return None

    def match_research_protocol(self, content):
        """Match content against research_protocol patterns (topics without skills)."""
        for item in self.get_research_protocol():
            pattern = item.get("pattern", "")
            key = f"research_{pattern[:30]}"
            compiled = self._compiled_patterns.get(key)
            if compiled and compiled.search(content):
                return item
        return None


# ============================================================================
# Code Skill Enforcer Hook (protocol.py base class)
# ============================================================================

class CodeSkillEnforcer(BaseHook):
    """
    Skill-First Enforcement via PreToolUse and PostToolUse events.

    PRE Mode (blocks until skill activated):
      Level B: Directory rules (.claude/hooks/ -> create-hook)
      Level A: Content patterns (StateGraph -> langgraph-core)
      Level C: Bash commands (docker compose -> deployment)

    POST Mode (advisory only, never blocks):
      Level F: LEARN phase (create skill tasks)
      Level E: Post-verification (must_contain, must_not_contain)
      Level D: Research cache reminder
    """

    def __init__(self):
        super().__init__()
        self.config = PatternConfig.get()

    def execute(self, inp: HookInput) -> Optional[HookOutput]:
        event = inp.detected_event

        if event == "PreToolUse":
            return self._handle_pre(inp)
        elif event == "PostToolUse":
            return self._handle_post(inp)

        return None

    # -------------------------------------------------------------------------
    # PRE Mode
    # -------------------------------------------------------------------------

    def _handle_pre(self, inp):
        # Level B: Directory rules (checked FIRST — most specific)
        result = self._check_directory_rules(inp)
        if result:
            return result

        # Level A: Content patterns (topics WITH dedicated skills)
        result = self._check_content_patterns(inp)
        if result:
            return result

        # Level A.1: Research protocol (topics WITHOUT dedicated skills)
        # BLOCKS and instructs Skill('learning-loop')
        result = self._check_research_protocol(inp)
        if result:
            return result

        # Level C: Bash commands
        result = self._check_bash_commands(inp)
        if result:
            return result

        return None

    def _extract_content(self, inp):
        """Extract content from Write or Edit tool input."""
        if inp.tool_name == "Write":
            return inp.tool_input.get("content", "")
        elif inp.tool_name == "Edit":
            return inp.tool_input.get("new_string", "")
        return ""

    def _normalize_path(self, file_path):
        """Normalize file path for directory rule matching."""
        normalized = file_path.replace("\\", "/")
        # Remove absolute path prefixes
        for prefix in ["D:/1C-Enterprise_Framework/", "D:/1\u0421-Framework/", "C:/Users/"]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        return normalized

    def _check_content_patterns(self, inp):
        """Level A: Check content against code-skill-patterns.json mappings."""
        content = self._extract_content(inp)
        if not content or len(content) < 20:
            return None

        match = self.config.match_pattern(content)
        if not match:
            return None

        skill = match.get("skill")
        label = match.get("label", skill)

        if SessionState and SessionState.is_skill_activated(skill):
            return None

        return HookOutput().block(
            f"SKILL REQUIRED: '{label}' ({skill})\n"
            f"Detected pattern: {match.get('pattern', '')[:50]}...\n\n"
            f"ACTIVATE THIS SKILL:\n"
            f"  Skill('{skill}')\n\n"
            f"Then retry your action."
        )

    def _check_directory_rules(self, inp):
        """Level B: Check file path against directory rules."""
        file_path = inp.tool_input.get("file_path", "")
        if not file_path:
            return None

        normalized = self._normalize_path(file_path)

        for rule in self.config.get_directory_rules():
            prefix = rule.get("directory_prefix", "")
            if normalized.startswith(prefix):
                skill = rule.get("skill")
                label = rule.get("label", skill)

                if SessionState and SessionState.is_skill_activated(skill):
                    return None

                return HookOutput().block(
                    f"SKILL REQUIRED: '{label}' ({skill})\n"
                    f"Directory: {prefix}\n"
                    f"File: {normalized}\n\n"
                    f"ACTIVATE THIS SKILL:\n"
                    f"  Skill('{skill}')\n\n"
                    f"Then retry your action."
                )

        return None

    def _check_research_protocol(self, inp):
        """Level A.1: Detect research_protocol patterns → BLOCK with learning-loop instruction.

        For topics WITHOUT dedicated skills (FastAPI, Redis, pytest, etc.).
        BLOCKS the write and instructs Claude to run Skill('learning-loop'),
        which triggers immediate subagent-based skill creation.
        """
        if inp.tool_name not in ("Write", "Edit"):
            return None

        content = self._extract_content(inp)
        if not content or len(content) < 30:
            return None

        match = self.config.match_research_protocol(content)
        if not match:
            return None

        if not SessionState:
            return None

        label = match.get("label", "unknown")
        domain = match.get("domain", "tech")
        pattern = match.get("pattern", "")
        label_key = label.lower().replace(" ", "-")

        # Dedup: skip if already triggered in this session
        if SessionState.is_skill_activated(f"learn:{label_key}"):
            return None

        # Mark as triggered (prevents repeated blocking)
        SessionState.add_activated_skill(f"learn:{label_key}")

        # Set pending_learn as backup for Level F
        if not SessionState.has_pending_learn():
            SessionState.set_pending_learn({
                "label": label,
                "domain": domain,
                "pattern": pattern,
            })

        return HookOutput().block(
            f"LEARNING REQUIRED: '{label}' — no dedicated skill exists.\n"
            f"Detected: {pattern[:60]}...\n"
            f"Domain: {domain}\n\n"
            f"ACTIVATE: Skill('learning-loop')\n\n"
            f"The learning-loop will:\n"
            f"1. SEARCH existing skills\n"
            f"2. FETCH knowledge from trusted sources\n"
            f"3. EXECUTE task via subagent with collected knowledge\n"
            f"4. VERIFY result against sources\n"
            f"5. CREATE new skill for future use\n\n"
            f"Then retry your Write/Edit."
        )

    def _check_bash_commands(self, inp):
        """Level C: Check bash command against rules."""
        if inp.tool_name != "Bash":
            return None

        command = inp.tool_input.get("command", "")
        if not command:
            return None

        match = self.config.match_bash(command)
        if not match:
            return None

        skill = match.get("skill")
        label = match.get("label", skill)

        if SessionState and SessionState.is_skill_activated(skill):
            return None

        return HookOutput().block(
            f"SKILL REQUIRED: '{label}' ({skill})\n"
            f"Command: {command[:100]}...\n\n"
            f"ACTIVATE THIS SKILL:\n"
            f"  Skill('{skill}')\n\n"
            f"Then retry your action."
        )

    # -------------------------------------------------------------------------
    # POST Mode (advisory only — PostToolUse cannot block)
    # -------------------------------------------------------------------------

    def _handle_post(self, inp):
        # Level F: LEARN phase
        result = self._check_learn_phase(inp)
        if result:
            return result

        # Level E: Post-verification
        result = self._check_post_verification(inp)
        if result:
            return result

        # Level D: Research cache reminder
        if inp.tool_name in ("WebSearch", "WebFetch"):
            return HookOutput().system_message(
                "[TIP] Check research cache before using search results: "
                ".claude/skills/tech-research/cache/"
            )

        return None

    def _check_post_verification(self, inp):
        """Level E: Verify written code against skill rules (advisory)."""
        if inp.tool_name not in ("Write", "Edit"):
            return None

        file_path = inp.tool_input.get("file_path", "")
        content = self._extract_content(inp)
        if not file_path or not content:
            return None

        if not SessionState:
            return None
        activated = SessionState.get_already_activated()

        for rule in self.config.get_post_verification():
            skill = rule.get("name", "")
            if skill not in activated:
                continue

            file_pattern = rule.get("file_pattern", "")
            if not re.search(file_pattern, file_path, re.IGNORECASE):
                continue

            # Check must_contain
            for pattern in rule.get("must_contain", []):
                if not re.search(pattern, content):
                    msg = rule.get("error_message",
                        f"Missing pattern '{pattern}'")
                    return HookOutput().system_message(
                        f"[WARN] POST-VERIFICATION: {skill}\n{msg}"
                    )

            # Check must_not_contain
            for pattern in rule.get("must_not_contain", []):
                if re.search(pattern, content):
                    msg = rule.get("error_message",
                        f"Found anti-pattern '{pattern}'")
                    return HookOutput().system_message(
                        f"[WARN] POST-VERIFICATION: {skill}\n{msg}"
                    )

        return None

    def _check_learn_phase(self, inp):
        """Level F: Create tasks for skill creation after research protocol."""
        if inp.tool_name not in ("Write", "Edit"):
            return None

        if not SessionState:
            return None

        pending = SessionState.get_pending_learn()
        if not pending:
            return None

        try:
            if has_recent_completion and has_recent_completion(
                "code-skill-enforcer", cooldown_minutes=10
            ):
                SessionState.clear_pending_learn()
                return None
        except Exception:
            pass

        label = pending.get("label", "unknown")

        tasks = [
            f"[LEARN] Create skill for '{label}'",
            f"[LEARN] Register '{label}' in skill-router-config.json",
        ]

        for task in tasks:
            try:
                if add_task:
                    add_task(
                        content=task,
                        created_by="code-skill-enforcer",
                        priority="mandatory"
                    )
            except Exception:
                pass

        SessionState.clear_pending_learn()

        return HookOutput().system_message(
            f"[LEARN] Created {len(tasks)} tasks for '{label}'."
        )


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    CodeSkillEnforcer().run()
