from datetime import timedelta

import pytest

from warehouse_twin import Command, Engine, default_config
from warehouse_twin.events import LocationSnapshot, ProductSnapshot, RobotSnapshot


def test_new_run_begins_with_run_started_in_adr_0002_envelope() -> None:
    config = default_config()
    engine = Engine.create(config, seed=42)

    first = engine.events[0]

    assert first.event_type == "run_started"
    assert first.sequence == 1
    assert first.simulation_tick == 0
    assert first.event_time == config.start_time
    assert first.entity_id == first.run_id
    assert first.schema_version == 1
    assert first.payload.seed == 42
    assert first.payload.config == config


def test_run_started_is_followed_by_reference_data_snapshots() -> None:
    engine = Engine.create(default_config(), seed=1)

    by_type: dict[str, list[str]] = {}
    for event in engine.events[1:]:
        by_type.setdefault(event.event_type, []).append(event.entity_id)

    assert by_type["product_snapshot"] == ["SKU-001", "SKU-002", "SKU-003", "SKU-004"]
    assert by_type["robot_snapshot"] == ["R1", "R2"]
    assert by_type["location_snapshot"] == [
        "A1", "A2",
        "S-A1-1", "S-A1-2", "S-A2-1", "S-A2-2",
        "PACK-1", "DOCK-1", "BACK-1", "CHG-1", "REPAIR-1",
    ]  # fmt: skip
    assert [e.sequence for e in engine.events] == list(range(1, 1 + 1 + 4 + 2 + 11))
    assert all(e.simulation_tick == 0 for e in engine.events)


def test_snapshots_carry_the_reference_attributes_streams_join_on() -> None:
    engine = Engine.create(default_config(), seed=1)
    products = {e.entity_id: e for e in engine.events if isinstance(e, ProductSnapshot)}
    robots = {e.entity_id: e for e in engine.events if isinstance(e, RobotSnapshot)}
    locations = {e.entity_id: e for e in engine.events if isinstance(e, LocationSnapshot)}

    assert products["SKU-003"].payload.name == "Desk lamp"
    assert (robots["R2"].payload.x, robots["R2"].payload.y) == (9, 2)
    assert robots["R2"].payload.load_capacity == 4
    assert locations["S-A2-1"].payload.location_type == "shelf_slot"
    assert locations["S-A2-1"].payload.sku == "SKU-003"
    assert locations["CHG-1"].payload.location_type == "charger"


def test_advancing_moves_simulated_time_and_snapshot_reflects_it() -> None:
    config = default_config()
    engine = Engine.create(config, seed=1)

    engine.advance(10)

    snapshot = engine.snapshot()
    assert snapshot.tick == 10
    assert snapshot.simulated_time == config.start_time + timedelta(seconds=10)
    assert snapshot.status == "running"
    assert snapshot.last_sequence == 18


def test_pause_command_emits_run_paused_at_its_tick_and_stops_time() -> None:
    engine = Engine.create(default_config(), seed=1)
    engine.submit(Command(tick=5, type="pause"))

    engine.advance(10)

    paused = [e for e in engine.events if e.event_type == "run_paused"]
    assert [e.simulation_tick for e in paused] == [5]
    assert engine.snapshot().tick == 5
    assert engine.snapshot().status == "paused"


def test_resume_command_restarts_time_and_emits_run_resumed() -> None:
    engine = Engine.create(default_config(), seed=1)
    engine.submit(Command(tick=2, type="pause"))
    engine.submit(Command(tick=2, type="resume"))

    engine.advance(5)

    types = [e.event_type for e in engine.events[-2:]]
    assert types == ["run_paused", "run_resumed"]
    assert engine.snapshot().tick == 5
    assert engine.snapshot().status == "running"


def test_end_command_emits_run_ended_and_freezes_the_run() -> None:
    engine = Engine.create(default_config(), seed=1)
    engine.submit(Command(tick=3, type="end"))

    engine.advance(10)
    events_after_end = engine.events
    engine.advance(10)

    assert events_after_end[-1].event_type == "run_ended"
    assert events_after_end[-1].simulation_tick == 3
    assert engine.events == events_after_end
    assert engine.snapshot().status == "ended"
    assert engine.snapshot().tick == 3


def test_command_stamped_in_the_past_is_rejected() -> None:
    engine = Engine.create(default_config(), seed=1)
    engine.advance(4)

    with pytest.raises(ValueError, match="tick"):
        engine.submit(Command(tick=3, type="pause"))


def test_resume_stamped_after_the_pause_tick_still_resumes_a_paused_run() -> None:
    engine = Engine.create(default_config(), seed=1)
    engine.submit(Command(tick=2, type="pause"))
    engine.submit(Command(tick=6, type="resume"))

    engine.advance(10)

    resumed = [e for e in engine.events if e.event_type == "run_resumed"]
    assert [e.simulation_tick for e in resumed] == [2]  # time was frozen at the pause
    assert engine.snapshot().status == "running"
    assert engine.snapshot().tick > 2


def test_pause_stamped_later_waits_for_its_tick_after_an_earlier_resume() -> None:
    engine = Engine.create(default_config(), seed=1)
    engine.submit(Command(tick=2, type="pause"))
    engine.submit(Command(tick=5, type="resume"))
    engine.submit(Command(tick=8, type="pause"))

    engine.advance(30)

    paused = [e.simulation_tick for e in engine.events if e.event_type == "run_paused"]
    assert paused == [2, 8]


def test_run_id_supplied_by_the_caller_need_not_be_a_uuid() -> None:
    engine = Engine.create(default_config(), seed=1, run_id="demo-run-1")

    assert engine.events[0].run_id == "demo-run-1"
    assert engine.events[0].event_id != engine.events[1].event_id
