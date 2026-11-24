import json
from datetime import UTC, datetime
from pathlib import Path

from warehouse_twin import Command, Engine, FileEventPublisher, default_config

COMMAND_LOG = [
    Command(tick=3, type="pause"),
    Command(tick=3, type="resume"),
    Command(tick=8, type="end"),
]


def _run_into(root: Path, wall_clock: datetime, seed: int) -> Path:
    publisher = FileEventPublisher(root, clock=lambda: wall_clock)
    engine = Engine.create(default_config(), seed=seed, publisher=publisher)
    for command in COMMAND_LOG:
        engine.submit(command)
    engine.advance(20)
    return root / engine.snapshot().run_id


def _without_emitted_at(run_dir: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for log in sorted(run_dir.glob("*.jsonl")):
        lines = []
        for line in log.read_text().splitlines():
            record = json.loads(line)
            del record["emitted_at"]
            lines.append(json.dumps(record, separators=(",", ":")))
        out[log.name] = ("\n".join(lines) + "\n").encode()
    return out


def test_same_seed_and_command_log_replay_byte_identical_events(tmp_path: Path) -> None:
    first = _run_into(tmp_path / "a", datetime(2030, 1, 1, tzinfo=UTC), seed=7)
    second = _run_into(tmp_path / "b", datetime(2031, 6, 6, tzinfo=UTC), seed=7)

    assert _without_emitted_at(first) == _without_emitted_at(second)
    assert first.name == second.name


def test_emitted_at_is_the_only_difference_between_replays(tmp_path: Path) -> None:
    first = _run_into(tmp_path / "a", datetime(2030, 1, 1, tzinfo=UTC), seed=7)
    second = _run_into(tmp_path / "b", datetime(2031, 6, 6, tzinfo=UTC), seed=7)

    assert (first / "runs.events.jsonl").read_bytes() != (second / "runs.events.jsonl").read_bytes()


def test_different_seed_is_a_different_run(tmp_path: Path) -> None:
    first = _run_into(tmp_path / "a", datetime(2030, 1, 1, tzinfo=UTC), seed=7)
    other = _run_into(tmp_path / "b", datetime(2030, 1, 1, tzinfo=UTC), seed=8)

    assert first.name != other.name
