"""Event publisher abstraction and the file-based append-only implementation."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from warehouse_twin.events import Event, stream_for


class EventPublisher(Protocol):
    """Where the engine sends events; it adds the wall-clock `emitted_at` (ADR-0002)."""

    def publish(self, event: Event) -> None: ...


def _utc_now() -> datetime:
    return datetime.now(UTC)


class FileEventPublisher:
    """Appends events as JSON lines: `<root>/<run_id>/<stream>.jsonl`."""

    def __init__(self, root: Path, clock: Callable[[], datetime] = _utc_now) -> None:
        self._root = root
        self._clock = clock

    def publish(self, event: Event) -> None:
        record = json.loads(event.model_dump_json())
        record["emitted_at"] = (
            self._clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
        )
        path = self._root / event.run_id / f"{stream_for(event)}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(json.dumps(record, separators=(",", ":")) + "\n")
