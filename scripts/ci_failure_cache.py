#!/usr/bin/env python3
"""CI Failure Cache + Analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".claude" / "cache"
JSONL_FILE = CACHE_DIR / "ci-failures.jsonl"
ISSUE_TAG_FILE = CACHE_DIR / "ci-failure-issues.json"
TEI_URL = "http://localhost:8080"
QDRANT_URL = "http://localhost:6333"
COLLECTION = "ci_failures"
COLLECTION_DIM = 1024
OCCURRENCE_THRESHOLD = 3
NOISE_PATTERNS = re.compile(
    r"##\[group\]|Prepare workflow|Set up Python|Install uv|Cache dependencies|"
    r"Initialize CodeQL|Post Run|safe\.directory|Cleaning up orphan|Post job cleanup",
    re.IGNORECASE)
