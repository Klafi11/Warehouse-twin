import asyncio
import json
from pathlib import Path

import pytest

from warehouse_twin.runner import SimulationRunner


def _event_types(log: Path) -> list[str]:
    lines = log.read_text().splitlines()
    return [json.loads(line)["event_type"] for line in lines]


def test_step_advances_one_tick_and_state_reports_it(tmp_path: Path) -> None:
    runner = SimulationRunner(tmp_path, seed=7)

    runner.step()
    runner.step()

    state = runner.state()
    assert state.snapshot.tick == 2
    assert state.snapshot.seed == 7
    assert state.snapshot.status == "running"
    assert state.speed == 1.0


def test_pause_and_resume_freeze_and_restart_simulated_time(tmp_path: Path) -> None:
    runner = SimulationRunner(tmp_path, seed=1)
    runner.step()

    runner.pause()
    assert runner.state().snapshot.status == "paused"
    runner.step()
    runner.step()
    assert runner.state().snapshot.tick == 1

    runner.resume()
    assert runner.state().snapshot.status == "running"
    assert runner.state().snapshot.tick == 2


def test_speed_is_validated_and_stored(tmp_path: Path) -> None:
    runner = SimulationRunner(tmp_path, seed=1)

    runner.set_speed(4)
    assert runner.state().speed == 4

    for bad in (0, -1, 1000):
        with pytest.raises(ValueError, match="speed"):
            runner.set_speed(bad)


def test_reset_starts_a_fresh_run_with_the_chosen_seed(tmp_path: Path) -> None:
    runner = SimulationRunner(tmp_path, seed=1)
    runner.step()
    old_run_id = runner.state().snapshot.run_id

    runner.reset(seed=2)

    snapshot = runner.state().snapshot
    assert snapshot.seed == 2
    assert snapshot.tick == 0
    assert snapshot.status == "running"
    assert snapshot.run_id != old_run_id


def test_reset_with_the_same_seed_does_not_collide_in_the_log(tmp_path: Path) -> None:
    runner = SimulationRunner(tmp_path, seed=1)
    runner.reset(seed=1)
    runner.reset(seed=1)

    assert runner.state().snapshot.seed == 1
    assert len(list(tmp_path.glob("*/*/runs.events.jsonl"))) == 3


def test_reset_ends_the_previous_run_in_its_log(tmp_path: Path) -> None:
    runner = SimulationRunner(tmp_path, seed=1)
    first_log = next(tmp_path.glob("*/*/runs.events.jsonl"))
    runner.step()

    runner.reset(seed=2)

    assert _event_types(first_log)[-1] == "run_ended"


def test_event_log_files_are_written(tmp_path: Path) -> None:
    runner = SimulationRunner(tmp_path, seed=1)
    runner.pause()

    logs = list(tmp_path.glob("*/*/runs.events.jsonl"))
    assert len(logs) == 1
    assert _event_types(logs[0]) == ["run_started", "run_paused"]


def _events_without_wall_clock(runner: SimulationRunner) -> list[str]:
    return [e.model_dump_json() for e in runner._engine.events]  # noqa: SLF001


def test_speed_changes_pacing_not_results(tmp_path: Path) -> None:
    async def drive(speed: float, root: Path) -> tuple[list[float], list[str]]:
        sleeps: list[float] = []
        runner = SimulationRunner(root, seed=5, speed=speed)

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)
            if len(sleeps) == 20:
                raise asyncio.CancelledError

        runner.pause()
        with pytest.raises(asyncio.CancelledError):
            await runner.run(sleep=fake_sleep)
        return sleeps, _events_without_wall_clock(runner)

    async def scenario() -> None:
        slow_sleeps, slow_events = await drive(1, tmp_path / "slow")
        fast_sleeps, fast_events = await drive(10, tmp_path / "fast")
        assert slow_events == fast_events
        assert slow_sleeps[0] == pytest.approx(fast_sleeps[0] * 10)

    asyncio.run(scenario())


def test_ticking_to_the_same_tick_at_any_speed_gives_identical_events(tmp_path: Path) -> None:
    slow = SimulationRunner(tmp_path / "a", seed=5, speed=1)
    fast = SimulationRunner(tmp_path / "b", seed=5, speed=50)
    for runner in (slow, fast):
        for _ in range(30):
            runner.step()

    assert _events_without_wall_clock(slow) == _events_without_wall_clock(fast)
    assert slow.state().snapshot == fast.state().snapshot


def test_run_loop_notifies_listeners_with_each_state(tmp_path: Path) -> None:
    async def scenario() -> list[int]:
        runner = SimulationRunner(tmp_path, seed=1)
        ticks: list[int] = []
        runner.subscribe(lambda state: ticks.append(state.snapshot.tick))
        count = 0

        async def fake_sleep(_: float) -> None:
            nonlocal count
            count += 1
            if count == 3:
                raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await runner.run(sleep=fake_sleep)
        return ticks

    assert asyncio.run(scenario()) == [1, 2, 3]
