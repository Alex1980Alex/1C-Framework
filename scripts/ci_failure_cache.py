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
