from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


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

    def to_dict(self) -> dict:
        return {
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
        }


class TelemetryWriter(Protocol):
    def write(self, event: RenameTelemetryEvent) -> None: ...


class JsonlTelemetryWriter:
    def __init__(
        self,
        path: Path,
        *,
        rotate_daily: bool = True,
        redact_names: bool = False,
    ) -> None:
        self._base_path = Path(path)
        self._rotate_daily = rotate_daily
        self._redact_names = redact_names
        self._lock = threading.Lock()
        self._base_path.parent.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self) -> Path:
        if not self._rotate_daily:
            return self._base_path
        today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")  # noqa: UP017
        return (
            self._base_path.parent
            / f"{self._base_path.stem}-{today}{self._base_path.suffix}"
        )

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
        with self._lock:
            target = self._resolve_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.write("\n")


class NullTelemetryWriter:
    def write(self, event: RenameTelemetryEvent) -> None:
        return None
