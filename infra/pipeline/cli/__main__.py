"""
Pipeline CLI Entry Point.

Позволяет запускать CLI как модуль:
    python -m shared.pipeline.cli run --project MyProject
"""

import sys
from .main import main

if __name__ == "__main__":
    sys.exit(main())
