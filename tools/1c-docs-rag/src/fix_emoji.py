#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fix emoji encoding issues in Python files"""

import re
import sys
from pathlib import Path

# Mapping of emoji to text replacements
EMOJI_REPLACEMENTS = {
    '✅': '[OK]',
    '❌': '[ERROR]',
    '⚠️': '[WARNING]',
    '🔍': '[SEARCH]',
    '📊': '[STATS]',
    '📁': '[FOLDER]',
    '📄': '[FILE]',
    '💾': '[SAVE]',
    '🔧': '[CONFIG]',
    '📝': '[NOTE]',
    '🚀': '[START]',
    '⏱️': '[TIME]',
    '💡': '[INFO]',
    '🎯': '[TARGET]',
    '📋': '[LIST]',
    '🔄': '[SYNC]',
    '✨': '[NEW]',
    '🗑️': '[DELETE]',
    '📦': '[PACKAGE]',
    '🌐': '[WEB]',
    '📚': '[DOCS]',
    '🎨': '[STYLE]',
    '🐛': '[BUG]',
    '⏰': '[TIME]',
    '🔗': '[LINK]',
}

def fix_emoji_in_file(file_path: str):
    """Replace all emoji in a file with text equivalents"""
    file_path = Path(file_path)

    if not file_path.exists():
        print(f"[ERROR] File not found: {file_path}")
        return False

    try:
        # Read file with UTF-8 encoding
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace all emoji
        modified = content
        replacements_made = 0
        for emoji, replacement in EMOJI_REPLACEMENTS.items():
            if emoji in modified:
                count = modified.count(emoji)
                modified = modified.replace(emoji, replacement)
                replacements_made += count
                print(f"[OK] Replaced {count}x emoji with '{replacement}'")

        # Write back if changes were made
        if replacements_made > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(modified)
            print(f"[OK] Fixed {replacements_made} emoji in {file_path.name}")
            return True
        else:
            print(f"[INFO] No emoji found in {file_path.name}")
            return True

    except Exception as e:
        print(f"[ERROR] Failed to process {file_path}: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_emoji.py <file1> [file2] ...")
        sys.exit(1)

    for file_path in sys.argv[1:]:
        print(f"\n[START] Processing {file_path}")
        fix_emoji_in_file(file_path)
