"""Tests for History-Aware Query Reformulator (Phase 9.2).

Tests parsing and helper functions without LLM calls.
"""

import pytest

from src.pdf_framework.agents.memory.conversation import Message
from src.pdf_framework.agents.rag.nodes.reformulator import (
    _format_history,
    _get_reformulation_prompt,
    _parse_reformulated_query,
    _should_reformulate,
)


class TestFormatHistory:
    """Test _format_history helper."""

    def test_empty_history(self):
        result = _format_history([])
        assert "No previous conversation" in result

    def test_single_user_message(self):
        msgs = [Message(role="user", content="What is PostgreSQL?")]
        result = _format_history(msgs)
        assert "User: What is PostgreSQL?" in result

    def test_user_and_assistant(self):
        msgs = [
            Message(role="user", content="What is PostgreSQL?"),
            Message(role="assistant", content="PostgreSQL is a RDBMS."),
        ]
        result = _format_history(msgs)
        assert "User: What is PostgreSQL?" in result
        assert "Assistant: PostgreSQL is a RDBMS." in result

    def test_multiple_turns(self):
        msgs = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
            Message(role="user", content="Q2"),
            Message(role="assistant", content="A2"),
        ]
        result = _format_history(msgs)
        lines = result.strip().split("\n")
        assert len(lines) == 4


class TestParseReformulatedQuery:
    """Test _parse_reformulated_query parser."""

    def test_plain_text(self):
        assert _parse_reformulated_query("How do I install PostgreSQL?") == "How do I install PostgreSQL?"

    def test_removes_rewritten_prefix(self):
        assert _parse_reformulated_query("Rewritten: How do I install PostgreSQL?") == "How do I install PostgreSQL?"

    def test_removes_query_prefix(self):
        assert _parse_reformulated_query("Query: What is 1C?") == "What is 1C?"

    def test_removes_double_quotes(self):
        assert _parse_reformulated_query('"How do I install PostgreSQL?"') == "How do I install PostgreSQL?"

    def test_removes_single_quotes(self):
        assert _parse_reformulated_query("'How do I install PostgreSQL?'") == "How do I install PostgreSQL?"

    def test_strips_whitespace(self):
        assert _parse_reformulated_query("  Hello world  ") == "Hello world"

    def test_empty_string(self):
        assert _parse_reformulated_query("") == ""

    def test_preserves_internal_quotes(self):
        result = _parse_reformulated_query('What does "1C" mean?')
        assert result == 'What does "1C" mean?'


class TestGetReformulationPrompt:
    """Test _get_reformulation_prompt builder."""

    def test_includes_history(self):
        prompt = _get_reformulation_prompt("User: Hello\nAssistant: Hi", "How about X?")
        assert "User: Hello" in prompt
        assert "How about X?" in prompt

    def test_includes_latest_query(self):
        prompt = _get_reformulation_prompt("", "Test query")
        assert "Test query" in prompt


class TestShouldReformulate:
    """Test _should_reformulate decision function."""

    def test_no_history_returns_false(self):
        state = {"question": "What is 1C?", "chat_history": []}
        assert _should_reformulate(state) is False

    def test_with_history_returns_true(self):
        state = {
            "question": "What about it?",
            "chat_history": [Message(role="user", content="Tell me about 1C")],
        }
        assert _should_reformulate(state) is True

    def test_disabled_returns_false(self):
        state = {
            "question": "What about it?",
            "chat_history": [Message(role="user", content="Hello")],
            "disable_reformulation": True,
        }
        assert _should_reformulate(state) is False

    def test_missing_history_key_returns_false(self):
        state = {"question": "Test"}
        assert _should_reformulate(state) is False
