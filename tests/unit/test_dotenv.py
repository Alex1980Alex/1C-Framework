"""Unit-тесты scripts/_dotenv.load_dotenv (ADR-041 follow-up: централизация секретов в .env). marker: unit."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
_spec = importlib.util.spec_from_file_location("_dotenv_t", _SCRIPTS / "_dotenv.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_loads_keys_and_strips_quotes(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('SONAR_TOKEN=abc123\nSONAR_HOST_URL="http://x:9000"\n# c\n\n', encoding="utf-8")
    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    monkeypatch.delenv("SONAR_HOST_URL", raising=False)
    assert mod.load_dotenv(str(env)) == 2
    assert os.environ["SONAR_TOKEN"] == "abc123"
    assert os.environ["SONAR_HOST_URL"] == "http://x:9000"  # кавычки сняты


def test_env_wins_over_dotenv(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("SONAR_TOKEN=from_dotenv\n", encoding="utf-8")
    monkeypatch.setenv("SONAR_TOKEN", "from_env")
    mod.load_dotenv(str(env))
    assert os.environ["SONAR_TOKEN"] == "from_env"  # env > .env: не перезаписан


def test_missing_file_noop(tmp_path):
    assert mod.load_dotenv(str(tmp_path / "nope.env")) == 0


def test_ignores_comments_blanks_and_badlines(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# c\n\nKEY1=v1\nbadline_no_eq\nKEY2=v2\n", encoding="utf-8")
    monkeypatch.delenv("KEY1", raising=False)
    monkeypatch.delenv("KEY2", raising=False)
    assert mod.load_dotenv(str(env)) == 2
    assert os.environ["KEY1"] == "v1" and os.environ["KEY2"] == "v2"


def test_corrupt_encoding_noop(tmp_path):
    # не-UTF-8 .env → graceful (broad except), не кидает (рек. code-verify)
    env = tmp_path / ".env"
    env.write_bytes(b"\xff\xfe BAD \x00 not-utf8 =x")
    assert mod.load_dotenv(str(env)) == 0
