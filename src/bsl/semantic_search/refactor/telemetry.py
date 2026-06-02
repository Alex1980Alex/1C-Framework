from __future__ import annotations

import gzip
import hashlib
import json
import logging
import re
import shutil
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class RenameTelemetryEvent:
    timestamp: str
    uri: str
    symbol_kind: str
    old_name: str | None
    new_name: str
    primary_backend: str | None
    fallback_used: bool
    applied: bool
    rolled_back: bool
    duration_ms: int
    error_code: str | None
    classifier_confidence: float
    matrix_confidence: float
    token_matched: bool | None
    prefilter_used: bool = False
    prefilter_dropped: int = 0
    version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "uri": self.uri,
            "symbol_kind": self.symbol_kind,
            "old_name": self.old_name,
            "new_name": self.new_name,
            "primary_backend": self.primary_backend,
            "fallback_used": self.fallback_used,
            "applied": self.applied,
            "rolled_back": self.rolled_back,
            "duration_ms": self.duration_ms,
            "error_code": self.error_code,
            "classifier_confidence": self.classifier_confidence,
            "matrix_confidence": self.matrix_confidence,
            "token_matched": self.token_matched,
            "prefilter_used": self.prefilter_used,
            "prefilter_dropped": self.prefilter_dropped,
        }


class TelemetryWriter(Protocol):
    def write(self, event: RenameTelemetryEvent) -> None: ...


class JsonlTelemetryWriter:
    _DATE_PATTERN = re.compile(r"^(?P<stem>.+)-(?P<date>\d{4}-\d{2}-\d{2})(?P<suffix>\.[^.]+)$")

    def __init__(
        self,
        path: Path,
        *,
        rotate_daily: bool = True,
        redact_names: bool = False,
        compress_after_days: int = 30,
    ) -> None:
        self._base_path = Path(path)
        self._rotate_daily = rotate_daily
        self._redact_names = redact_names
        self._compress_after_days = compress_after_days
        self._lock = threading.Lock()
        self._last_compress_check: float = 0.0
        self._base_path.parent.mkdir(parents=True, exist_ok=True)
        self.compress_old_files()

    def _resolve_path(self) -> Path:
        if not self._rotate_daily:
            return self._base_path
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")  # noqa: UP017
        return self._base_path.parent / f"{self._base_path.stem}-{today}{self._base_path.suffix}"

    @staticmethod
    def _sha1(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8")).hexdigest()

    def write(self, event: RenameTelemetryEvent) -> None:
        record = event.to_dict()
        if self._redact_names:
            if record["old_name"] is not None:
                record["old_name"] = self._sha1(record["old_name"])
            record["new_name"] = self._sha1(record["new_name"])
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        should_compress = False
        with self._lock:
            target = self._resolve_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")
            now = time.monotonic()
            if now - self._last_compress_check >= 3600:
                self._last_compress_check = now
                should_compress = True
        # Compression touches only rotated (non-active) files, so it runs
        # outside the write lock to avoid blocking concurrent writers.
        if should_compress:
            self.compress_old_files()

    def compress_old_files(self) -> None:
        """Gzip-compress rotated files older than `compress_after_days`. Best-effort."""
        if self._compress_after_days <= 0:
            return

        cutoff = datetime.now(tz=timezone.utc) - timedelta(days=self._compress_after_days)  # noqa: UP017
        parent = self._base_path.parent
        stem = self._base_path.stem
        suffix = self._base_path.suffix

        if not parent.is_dir():
            return

        try:
            entries = list(parent.iterdir())
        except OSError:
            logger.warning("Failed to list %s for compression", parent, exc_info=True)
            return

        for entry in entries:
            if not entry.is_file() or entry.suffix == ".gz":
                continue
            match = self._DATE_PATTERN.match(entry.name)
            if not match or match["stem"] != stem or match["suffix"] != suffix:
                continue
            try:
                file_date = datetime.strptime(match["date"], "%Y-%m-%d").replace(tzinfo=UTC)
            except ValueError:
                continue
            if file_date >= cutoff:
                continue

            gz_path = entry.with_suffix(entry.suffix + ".gz")
            if gz_path.exists():
                continue
            try:
                with entry.open("rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                entry.unlink()
            except OSError:
                logger.warning("Failed to compress %s", entry, exc_info=True)
                if gz_path.exists():
                    try:
                        gz_path.unlink()
                    except OSError:
                        pass


class NullTelemetryWriter:
    def write(self, event: RenameTelemetryEvent) -> None:
        return None
