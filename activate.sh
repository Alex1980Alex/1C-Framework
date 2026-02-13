#!/bin/bash
# Portable activation script for Linux/Mac
# Usage: source activate.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.venv/bin/activate" 2>/dev/null || source "$SCRIPT_DIR/.venv/Scripts/activate"
echo "[OK] Virtual environment activated"
echo "Python: $(python --version)"
echo "Project: $SCRIPT_DIR"
