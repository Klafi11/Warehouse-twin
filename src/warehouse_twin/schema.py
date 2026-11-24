"""JSON Schema generated from the event models (ADR-0003).

`uv run python -m warehouse_twin.schema` writes `schemas/events.v<N>.schema.json` for the
current `SCHEMA_VERSION`. A committed version file is immutable: changing the models
without bumping the version makes the schema test fail.
"""

import json
import sys
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from warehouse_twin.events import SCHEMA_VERSION, EventModel

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def schema_file(version: int) -> str:
    return f"events.v{version}.schema.json"


def generate_event_schema() -> dict[str, Any]:
    return TypeAdapter(EventModel).json_schema()


def main() -> int:
    path = SCHEMA_DIR / schema_file(SCHEMA_VERSION)
    schema = generate_event_schema()
    if path.exists() and json.loads(path.read_text()) != schema:
        print(f"{path.name} exists and differs: bump SCHEMA_VERSION first.", file=sys.stderr)
        return 1
    SCHEMA_DIR.mkdir(exist_ok=True)
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
