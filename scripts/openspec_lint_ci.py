#!/usr/bin/env python3
"""openspec_lint_ci.py — CI-friendly линтер OpenSpec change'ей.

Используется в .github/workflows/openspec.yml и .pre-commit-config.yaml.
"""
from __future__ import annotations
import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

# skeleton — implementation appended below via edits
