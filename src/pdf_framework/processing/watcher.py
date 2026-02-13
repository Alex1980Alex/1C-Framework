"""PDF File Watcher for Incremental Indexing (Phase 18).

Monitors a directory for PDF changes and triggers re-indexing callbacks.

Author: Claude Code
Version: 1.0.0 - Phase 18: Incremental Indexing
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class PDFFileWatcher:
    """Watch a directory for PDF file changes and trigger indexing.

    Uses polling (cross-platform) with debounce to detect:
    - New PDF files → callback("index", path)
    - Modified PDF files → callback("reindex", path)
    - Deleted PDF files → callback("delete", path)
    """

    def __init__(
        self,
        watch_dir: str | Path,
        indexing_callback: Callable[[str, str], Coroutine[Any, Any, None]],
        poll_interval: float = 2.0,
        debounce_seconds: float = 5.0,
        extensions: tuple[str, ...] = (".pdf",),
    ):
        self._watch_dir = Path(watch_dir)
        self._callback = indexing_callback
        self._poll_interval = poll_interval
        self._debounce_seconds = debounce_seconds
        self._extensions = extensions
        self._known_files: dict[str, float] = {}  # path → mtime
        self._running = False
        self._task: asyncio.Task | None = None
        self._pending: dict[str, tuple[str, float]] = {}  # path → (event_type, first_seen)

    async def start(self) -> None:
        """Start watching in the background."""
        self._running = True
        # Snapshot existing files
        self._known_files = self._scan()
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(f"[WATCHER] Started watching {self._watch_dir} ({len(self._known_files)} existing files)")

    async def stop(self) -> None:
        """Stop watching and flush pending events."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Flush any remaining pending events
        for fpath, (event_type, _) in list(self._pending.items()):
            await self._callback(event_type, fpath)
        self._pending.clear()

    def _scan(self) -> dict[str, float]:
        """Scan directory for matching files and their mtimes."""
        result: dict[str, float] = {}
        if not self._watch_dir.exists():
            return result
        for f in self._watch_dir.iterdir():
            if f.is_file() and f.suffix.lower() in self._extensions:
                result[str(f)] = f.stat().st_mtime
        return result

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                current = self._scan()
                now = asyncio.get_event_loop().time()

                # Detect new and modified files
                for fpath, mtime in current.items():
                    if fpath not in self._known_files:
                        self._pending[fpath] = ("index", now)
                    elif mtime != self._known_files[fpath]:
                        self._pending[fpath] = ("reindex", now)

                # Detect deleted files
                for fpath in self._known_files:
                    if fpath not in current:
                        self._pending[fpath] = ("delete", now)

                # Fire debounced events
                to_fire = [
                    (fp, evt)
                    for fp, (evt, first_seen) in self._pending.items()
                    if now - first_seen >= self._debounce_seconds
                ]
                for fpath, event_type in to_fire:
                    await self._callback(event_type, fpath)
                    del self._pending[fpath]

                self._known_files = current

            except Exception as e:
                logger.error(f"[WATCHER] Poll error: {e}")

            await asyncio.sleep(self._poll_interval)
