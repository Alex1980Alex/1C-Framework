"""Wrapper that captures all errors to a log file before running the real server."""

import os
import sys
import traceback

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "claude-startup.log")


def main():
    with open(LOG, "w", encoding="utf-8") as log:
        log.write("=== Startup ===\n")
        log.write(f"Python: {sys.executable}\n")
        log.write(f"Version: {sys.version}\n")
        log.write(f"CWD: {os.getcwd()}\n")
        log.write(f"Args: {sys.argv}\n")
        log.write(f"LAZY_MCP_CONFIG: {os.environ.get('LAZY_MCP_CONFIG', 'NOT SET')}\n")
        log.write(f"stdin: {sys.stdin}\n")
        log.write(f"stdout: {sys.stdout}\n")
        log.write(f"stderr: {sys.stderr}\n")
        log.flush()

        try:
            log.write("Importing server...\n")
            log.flush()

            # Import the real server's main
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import server

            log.write("Import OK. Running main()...\n")
            log.flush()

            import asyncio

            asyncio.run(server.main())

        except Exception as e:
            log.write(f"FATAL ERROR: {type(e).__name__}: {e}\n")
            log.write(traceback.format_exc())
            log.flush()
            raise


if __name__ == "__main__":
    main()
