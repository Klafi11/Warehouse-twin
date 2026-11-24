import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from warehouse_twin import Command, Engine, FileEventPublisher, default_config


def _fixed_clock() -> datetime:
    return datetime(2030, 5, 5, 12, 0, 0, tzinfo=UTC)


def _read(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_events_are_logged_one_file_per_stream_per_run(tmp_path: Path) -> None:
    publisher = FileEventPublisher(tmp_path, clock=_fixed_clock)
    engine = Engine.create(default_config(), seed=1, publisher=publisher)
    run_dir = tmp_path / engine.snapshot().run_id

    assert sorted(p.name for p in run_dir.iterdir()) == [
        "ref.locations.jsonl",
        "ref.products.jsonl",
        "ref.robots.jsonl",
        "runs.events.jsonl",
    ]
    assert len(_read(run_dir / "ref.products.jsonl")) == 4
    assert len(_read(run_dir / "ref.locations.jsonl")) == 11
    assert [e["event_type"] for e in _read(run_dir / "runs.events.jsonl")] == ["run_started"]


def test_publisher_stamps_wall_clock_emitted_at_on_each_logged_event(tmp_path: Path) -> None:
    publisher = FileEventPublisher(tmp_path, clock=_fixed_clock)
    engine = Engine.create(default_config(), seed=1, publisher=publisher)
    run_dir = tmp_path / engine.snapshot().run_id

    started = _read(run_dir / "runs.events.jsonl")[0]

    assert started["emitted_at"] == "2030-05-05T12:00:00Z"
    assert started["event_time"] == "2026-01-01T08:00:00Z"
    assert "emitted_at" not in engine.events[0].model_dump()


def test_log_is_append_only_as_the_run_progresses(tmp_path: Path) -> None:
    publisher = FileEventPublisher(tmp_path, clock=_fixed_clock)
    engine = Engine.create(default_config(), seed=1, publisher=publisher)
    log = tmp_path / engine.snapshot().run_id / "runs.events.jsonl"
    before = log.read_text()

    engine.submit(Command(tick=2, type="pause"))
    engine.advance(5)

    after = log.read_text()
    assert after.startswith(before)
    assert [e["event_type"] for e in _read(log)] == ["run_started", "run_paused"]


def test_starting_a_second_run_with_the_same_run_id_in_the_same_log_is_refused(
    tmp_path: Path,
) -> None:
    Engine.create(default_config(), seed=1, publisher=FileEventPublisher(tmp_path))

    with pytest.raises(FileExistsError):
        Engine.create(default_config(), seed=1, publisher=FileEventPublisher(tmp_path))
