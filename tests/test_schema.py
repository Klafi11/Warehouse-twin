import json
from pathlib import Path

from pydantic import TypeAdapter

from warehouse_twin import Engine, default_config
from warehouse_twin.events import SCHEMA_VERSION, EventModel
from warehouse_twin.schema import generate_event_schema, schema_file

SCHEMAS = Path(__file__).parent.parent / "schemas"


def test_generated_schema_matches_the_committed_file_for_the_current_schema_version() -> None:
    committed = json.loads((SCHEMAS / schema_file(SCHEMA_VERSION)).read_text())

    assert generate_event_schema() == committed, (
        "Event models changed without a schema_version bump. Bump SCHEMA_VERSION in "
        "events.py and run `uv run python -m warehouse_twin.schema` to write the new file."
    )


def test_every_emitted_event_round_trips_through_the_schema_models() -> None:
    engine = Engine.create(default_config(), seed=1)
    adapter = TypeAdapter(EventModel)

    for event in engine.events:
        assert adapter.validate_json(event.model_dump_json()) == event


def test_schema_covers_every_event_type_the_engine_emits() -> None:
    engine = Engine.create(default_config(), seed=1)
    schema = generate_event_schema()

    assert {e.event_type for e in engine.events} <= set(schema["discriminator"]["mapping"])
