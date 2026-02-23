#!/usr/bin/env python3
"""
Code Skill Enforcer — Skill-First Enforcement Hook

Event: PreToolUse | PostToolUse
Matcher: Write|Edit|Bash|WebSearch|WebFetch
Purpose: Enforce skill usage before/after code operations
Timeout: 3s

Principle:
  PRE (before)  -> Check skill cache -> BLOCK if missing -> ACTIVATE -> retry
  POST (after)  -> Verify vs skill -> CREATE LEARN tasks if needed

Levels:
  A: Content patterns (StateGraph -> langgraph-core)
  B: Directory rules (.claude/hooks/ -> create-hook)
  C: Bash commands (docker compose -> deployment)
  D: Research cache reminder (WebSearch "qdrant" -> check cache)
  E: Post-verification (must_contain, must_not_contain checks)
  F: LEARN phase (create skill tasks)

Author: Claude Code
Version: 1.0.0
Created: 2026-02-23
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Path resolution
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
_FRAMEWORK_HOOKS = os.path.join(os.path.dirname(_HOOK_DIR), "scripts", "claude-backend", ".claude", "hooks")

# Add to path in priority order
for hook_path in [_FRAMEWORK_HOOKS, _USER_HOOKS, _HOOK_DIR]:
    shared_path = os.path.join(hook_path, "shared")
    if os.path.isdir(shared_path):
        sys.path.insert(0, shared_path)
    base_path = os.path.join(hook_path, "base")
    if os.path.isdir(base_path):
        sys.path.insert(0, base_path)

# Imports
try:
    from base import BaseHook, HookInput, HookOutput, HookEvent, HookOutcome
    from session_state import SessionState
    from trust_scorer import TrustScorer
    from task_master import add_task, has_recent_completion
except ImportError as e:
    # Graceful degradation: allow import errors
    _import_error = str(e)
    BaseHook = None
    HookInput = None
    HookOutput = None
    HookEvent = None
    HookOutcome = None
    SessionState = None
    TrustScorer = None
    add_task = None
    has_recent_completion = None


# ============================================================================
# Configuration Loader (lazy-load with caching)
# ============================================================================

class PatternConfig:
    """Lazy-loaded pattern configuration with caching."""

    _instance: Optional["PatternConfig"] = None
    _config: Dict[str, Any] = None
    _compiled_patterns: Dict[str, re.Pattern] = {}

    CONFIG_PATH = os.path.join(_HOOK_DIR, "shared", "code-skill-patterns.json")

    @classmethod
    def get(cls) -> "PatternConfig":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize with lazy config loading."""
        if self._config is None:
            self._load_config()

    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        self._config = {
            "patterns": {"mappings": []},
            "directory_rules": {"mappings": []},
            "bash_rules": {"mappings": []},
            "research_rules": {"mappings": []},
            "research_protocol": {"patterns": []},
            "post_verification": {"rules": []}
        }

        try:
            if os.path.exists(self.CONFIG_PATH):
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    self._config.update(loaded)
        except (json.JSONDecodeError, IOError):
            pass  # Use default config

        # Pre-compile regex patterns for performance
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Pre-compile all regex patterns."""
        # Content patterns
        for mapping in self._config.get("patterns", {}).get("mappings", []):
            pattern = mapping.get("pattern", "")
            key = f"pattern_{pattern[:20]}"
            try:
                self._compiled_patterns[key] = re.compile(pattern, re.IGNORECASE)
            except re.error:
                pass

        # Bash rules
        for mapping in self._config.get("bash_rules", {}).get("mappings", []):
            pattern = mapping.get("pattern", "")
            key = f"bash_{pattern[:20]}"
            try:
                self._compiled_patterns[key] = re.compile(pattern, re.IGNORECASE)
            except re.error:
                pass

        # Research protocol
        for item in self._config.get("research_protocol", {}).get("patterns", []):
            pattern = item.get("pattern", "")
            key = f"research_{pattern[:20]}"
            try:
                self._compiled_patterns[key] = re.compile(pattern, re.IGNORECASE)
            except re.error:
                pass

    def get_patterns(self) -> List[Dict[str, Any]]:
        """Get content pattern mappings."""
        return self._config.get("patterns", {}).get("mappings", [])

    def get_directory_rules(self) -> List[Dict[str, Any]]:
        """Get directory rule mappings."""
        return self._config.get("directory_rules", {}).get("mappings", [])

    def get_bash_rules(self) -> List[Dict[str, Any]]:
        """Get bash rule mappings."""
        return self._config.get("bash_rules", {}).get("mappings", [])

    def get_research_protocol(self) -> List[Dict[str, Any]]:
        """Get research protocol patterns."""
        return self._config.get("research_protocol", {}).get("patterns", [])

    def get_post_verification(self) -> List[Dict[str, Any]]:
        """Get post-verification rules."""
        return self._config.get("post_verification", {}).get("rules", [])

    def match_pattern(self, content: str) -> Optional[Dict[str, Any]]:
        """Match content against patterns, return first match."""
        for mapping in self.get_patterns():
            pattern = mapping.get("pattern", "")
            key = f"pattern_{pattern[:20]}"
            compiled = self._compiled_patterns.get(key)

            if compiled and compiled.search(content):
                return mapping

        return None

    def match_bash(self, command: str) -> Optional[Dict[str, Any]]:
        """Match bash command against rules."""
        for mapping in self.get_bash_rules():
            pattern = mapping.get("pattern", "")
            key = f"bash_{pattern[:20]}"
            compiled = self._compiled_patterns.get(key)

            if compiled and compiled.search(command):
                return mapping

        return None

    def match_research_protocol(self, content: str) -> Optional[Dict[str, Any]]:
        """Match content against research protocol."""
        for item in self.get_research_protocol():
            pattern = item.get("pattern", "")
            key = f"research_{pattern[:20]}"
            compiled = self._compiled_patterns.get(key)

            if compiled and compiled.search(content):
                return item

        return None


# ============================================================================
# Code Skill Enforcer Hook
# ============================================================================

class CodeSkillEnforcer(BaseHook):
    """
    Main hook for Skill-First Enforcement.

    PRE Mode:
    - Level A: Content patterns (StateGraph -> langgraph-core)
    - Level B: Directory rules (.claude/hooks/ -> create-hook)
    - Level C: Bash commands (docker compose -> deployment)
    - Fallback: Research protocol for unknown patterns

    POST Mode:
    - Level D: Research cache reminder
    - Level E: Post-verification (must_contain, must_not_contain)
    - Level F: LEARN phase (create skill tasks)
    """

    HOOK_NAME = "CodeSkillEnforcer"
    HOOK_VERSION = "1.0.0"

    def __init__(self):
        super().__init__()
        self.config = PatternConfig.get()

    # -------------------------------------------------------------------------
    # PRE Mode: Content Patterns (Level A)
    # -------------------------------------------------------------------------

    def _check_content_patterns(self, inp: HookInput) -> Optional[HookOutput]:
        """
        Check content patterns (Level A).

        Returns HookOutput.block() if skill not activated.
        """
        content = self._extract_content(inp)
        if not content or len(content) < 20:
            return None

        # Match against patterns
        match = self.config.match_pattern(content)
        if not match:
            return None

        skill = match.get("skill")
        label = match.get("label", skill)

        # Check if skill is activated
        if SessionState and SessionState.is_skill_activated(skill):
            return None

        # Skill not activated - BLOCK
        output = HookOutput()
        output.block(
            f"SKILL REQUIRED: '{label}' ({skill})\n"
            f"Detected pattern: {match.get('pattern', '')[:50]}...\n\n"
            f"ACTIVATE THIS SKILL:\n"
            f"  Skill('skill:{skill}')\n\n"
            f"Then retry your action.",
            exit_code=2
        )
        return output

    def _extract_content(self, inp: HookInput) -> Optional[str]:
        """Extract content from Write or Edit tool input."""
        if inp.tool_name == "Write":
            return inp.tool_input.get("content", "")
        elif inp.tool_name == "Edit":
            return inp.tool_input.get("new_string", "")
        return None

    # -------------------------------------------------------------------------
    # PRE Mode: Directory Rules (Level B)
    # -------------------------------------------------------------------------

    def _check_directory_rules(self, inp: HookInput) -> Optional[HookOutput]:
        """
        Check directory rules (Level B).

        Returns HookOutput.block() if skill not activated.
        Directory rules are checked BEFORE content patterns.
        """
        file_path = inp.tool_input.get("file_path", "")
        if not file_path:
            return None

        # Normalize path
        normalized = self._normalize_path(file_path)

        # Match against directory rules
        for rule in self.config.get_directory_rules():
            prefix = rule.get("directory_prefix", "")
            if normalized.startswith(prefix):
                skill = rule.get("skill")
                label = rule.get("label", skill)

                # Check if skill is activated
                if SessionState and SessionState.is_skill_activated(skill):
                    return None

                # Skill not activated - BLOCK
                output = HookOutput()
                output.block(
                    f"SKILL REQUIRED: '{label}' ({skill})\n"
                    f"Directory: {prefix}\n"
                    f"File: {normalized}\n\n"
                    f"ACTIVATE THIS SKILL:\n"
                    f"  Skill('skill:{skill}')\n\n"
                    f"Then retry your action.",
                    exit_code=2
                )
                return output

        return None

    def _normalize_path(self, file_path: str) -> str:
        """Normalize file path for matching."""
        # Convert to forward slashes
        normalized = file_path.replace("\\", "/")

        # Remove absolute path prefixes
        # Try common project roots
        for prefix in ["D:/1C-Enterprise_Framework/", "D:/1С-Framework/", "C:/Users/"]:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break

        return normalized

    # -------------------------------------------------------------------------
    # PRE Mode: Bash Commands (Level C)
    # -------------------------------------------------------------------------

    def _check_bash_commands(self, inp: HookInput) -> Optional[HookOutput]:
        """
        Check bash commands (Level C).

        Returns HookOutput.block() if skill not activated.
        """
        if inp.tool_name != "Bash":
            return None

        command = inp.tool_input.get("command", "")
        if not command:
            return None

        # Match against bash rules
        match = self.config.match_bash(command)
        if not match:
            return None

        skill = match.get("skill")
        label = match.get("label", skill)

        # Check if skill is activated
        if SessionState and SessionState.is_skill_activated(skill):
            return None

        # Skill not activated - BLOCK
        output = HookOutput()
        output.block(
            f"SKILL REQUIRED: '{label}' ({skill})\n"
            f"Command: {command[:100]}...\n\n"
            f"ACTIVATE THIS SKILL:\n"
            f"  Skill('skill:{skill}')\n\n"
            f"Then retry your action.",
            exit_code=2
        )
        return output

    # -------------------------------------------------------------------------
    # PRE Mode: Research Protocol (Fallback)
    # -------------------------------------------------------------------------

    def _check_research_protocol(self, inp: HookInput) -> Optional[HookOutput]:
        """
        Check research protocol (fallback for unknown patterns).

        Returns HookOutput with advisory message.
        """
        content = self._extract_content(inp)
        if not content or len(content) < 20:
            return None

        # Match against research protocol
        match = self.config.match_research_protocol(content)
        if not match:
            return None

        label = match.get("label")
        domain = match.get("domain", "tech")

        # Generate research protocol message
        if TrustScorer:
            protocol = TrustScorer.get_research_protocol(domain, label)
        else:
            protocol = f"""## Research Protocol: {label}

You are about to implement code for **{label}**.
Before writing any code, consult trusted sources:
- Official documentation
- Community resources (StackOverflow, GitHub)
- Best practices guides

After researching, apply knowledge and write code following best practices.
"""

        # Set pending learn for LEARN phase
        if SessionState:
            SessionState.set_pending_learn({
                "label": label,
                "domain": domain,
                "pattern": match.get("pattern", "")
            })

        # ADVISE (not block)
        output = HookOutput()
        output.advise(protocol)
        return output

    # -------------------------------------------------------------------------
    # POST Mode: Research Cache Reminder (Level D)
    # -------------------------------------------------------------------------

    def _check_research_cache(self, inp: HookInput) -> Optional[HookOutput]:
        """
        Check research cache (Level D).

        Returns HookOutput with cache reminder for WebSearch/WebFetch.
        """
        if inp.tool_name not in ("WebSearch", "WebFetch"):
            return None

        query = inp.tool_input.get("query", "") or inp.tool_input.get("url", "")
        if not query:
            return None

        # Check if query matches research rules
        # (Would need config extension for full implementation)
        output = HookOutput()
        output.advise(
            "💡 RESEARCH CACHE REMINDER\n"
            "Before using search results, check if information is cached:\n"
            "- .claude/skills/tech-research/cache/\n"
            "- 1c-docs-rag via mcp__1c-docs-rag__search_docs()\n"
            "- bsl-semantic-search for BSL patterns"
        )
        return output

    # -------------------------------------------------------------------------
    # POST Mode: Post-Verification (Level E)
    # -------------------------------------------------------------------------

    def _check_post_verification(self, inp: HookInput) -> Optional[HookOutput]:
        """
        Post-write verification (Level E).

        Returns HookOutput with advisory + creates task if verification fails.
        """
        if inp.tool_name not in ("Write", "Edit"):
            return None

        file_path = inp.tool_input.get("file_path", "")
        content = self._extract_content(inp)

        if not file_path or not content:
            return None

        # Get activated skills
        if not SessionState:
            return None
        activated = SessionState.get_already_activated()

        # Check each post-verification rule
        for rule in self.config.get_post_verification():
            skill = rule.get("name", "")
            if skill not in activated:
                continue

            # Check file pattern
            file_pattern = rule.get("file_pattern", "")
            if not re.search(file_pattern, file_path, re.IGNORECASE):
                continue

            # Check must_contain
            must_contain = rule.get("must_contain", [])
            for pattern in must_contain:
                if not re.search(pattern, content):
                    # Verification failed
                    error_msg = rule.get("error_message",
                        f"Post-verification failed: missing pattern '{pattern}'")

                    output = HookOutput()
                    output.advise(
                        f"⚠️ POST-VERIFICATION FAILED\n"
                        f"Skill: {skill}\n"
                        f"File: {file_path}\n"
                        f"Issue: {error_msg}\n\n"
                        f"Please fix and retry."
                    )

                    # Create mandatory task
                    try:
                        add_task(
                            content=f"[MANDATORY] Fix post-verification failure: {skill}",
                            created_by="code-skill-enforcer",
                            priority="mandatory"
                        )
                    except Exception:
                        pass

                    return output

            # Check must_not_contain
            must_not_contain = rule.get("must_not_contain", [])
            for pattern in must_not_contain:
                if re.search(pattern, content):
                    # Verification failed
                    error_msg = rule.get("error_message",
                        f"Post-verification failed: found anti-pattern '{pattern}'")

                    output = HookOutput()
                    output.advise(
                        f"⚠️ POST-VERIFICATION FAILED\n"
                        f"Skill: {skill}\n"
                        f"File: {file_path}\n"
                        f"Issue: {error_msg}\n\n"
                        f"Please fix and retry."
                    )

                    # Create mandatory task
                    try:
                        add_task(
                            content=f"[MANDATORY] Fix post-verification failure: {skill}",
                            created_by="code-skill-enforcer",
                            priority="mandatory"
                        )
                    except Exception:
                        pass

                    return output

        return None

    # -------------------------------------------------------------------------
    # POST Mode: LEARN Phase (Level F)
    # -------------------------------------------------------------------------

    def _check_learn_phase(self, inp: HookInput) -> Optional[HookOutput]:
        """
        LEARN phase (Level F).

        Creates tasks for skill creation after research protocol was triggered.
        """
        if inp.tool_name not in ("Write", "Edit"):
            return None

        if not SessionState:
            return None

        # Check for pending learn
        pending = SessionState.get_pending_learn()
        if not pending:
            return None

        # Check cooldown to prevent spam
        try:
            if has_recent_completion("code-skill-enforcer", cooldown_minutes=10):
                SessionState.clear_pending_learn()
                return None
        except Exception:
            pass

        label = pending.get("label", "unknown")
        domain = pending.get("domain", "tech")

        # Create 3 LEARN tasks
        tasks = [
            f"[LEARN] Create skill for '{label}' using doc-to-skill pattern",
            f"[LEARN] Register '{label}' in skill-router-config.json",
            f"[LEARN] Migrate '{label}' from research_protocol to patterns section"
        ]

        for task in tasks:
            try:
                add_task(
                    content=task,
                    created_by="code-skill-enforcer",
                    priority="mandatory"
                )
            except Exception:
                pass

        # Clear pending learn
        SessionState.clear_pending_learn()

        output = HookOutput()
        output.advise(
            f"📚 LEARN PHASE: '{label}'\n"
            f"Created {len(tasks)} tasks to capture this knowledge.\n"
            f"Complete these tasks to add '{label}' to skill cache."
        )
        return output

    # -------------------------------------------------------------------------
    # Main Hook Logic
    # -------------------------------------------------------------------------

    def run(self, inp: HookInput) -> HookOutput:
        """
        Main hook execution.

        Routes to appropriate handler based on event type.
        """
        # Skip non-tool events
        if not inp.is_pre_tool_use() and not inp.is_post_tool_use():
            return HookOutput()

        # PRE Mode checks
        if inp.is_pre_tool_use():
            # Level B: Directory rules (checked FIRST)
            dir_output = self._check_directory_rules(inp)
            if dir_output:
                return dir_output

            # Level A: Content patterns
            content_output = self._check_content_patterns(inp)
            if content_output:
                return content_output

            # Level C: Bash commands
            bash_output = self._check_bash_commands(inp)
            if bash_output:
                return bash_output

            # Research protocol (fallback)
            research_output = self._check_research_protocol(inp)
            if research_output:
                return research_output

        # POST Mode checks
        elif inp.is_post_tool_use():
            # Level F: LEARN phase (checked FIRST)
            learn_output = self._check_learn_phase(inp)
            if learn_output:
                return learn_output

            # Level E: Post-verification
            verify_output = self._check_post_verification(inp)
            if verify_output:
                return verify_output

            # Level D: Research cache reminder
            cache_output = self._check_research_cache(inp)
            if cache_output:
                return cache_output

        # Default: allow
        return HookOutput()


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    if BaseHook is None:
        # Graceful degradation
        sys.exit(0)

    CodeSkillEnforcer.main()
