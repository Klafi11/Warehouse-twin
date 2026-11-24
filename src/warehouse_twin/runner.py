"""Paces the engine in real time and applies presenter controls.

The runner owns wall-clock concerns the pure engine must not: how fast ticks are
delivered, and which log directory a Run writes to. Speed only changes the sleep
between ticks, never what a tick does.
"""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from warehouse_twin.commands import Command
from warehouse_twin.config import WarehouseConfig, default_config
from warehouse_twin.engine import Engine, EngineSnapshot
from warehouse_twin.publisher import FileEventPublisher

BASE_TICKS_PER_SECOND = 5.0
MIN_SPEED = 0.1
MAX_SPEED = 100.0

Sleep = Callable[[float], Awaitable[None]]


class RunnerState(BaseModel):
    """What the UI sees: the engine snapshot plus the pacing multiplier."""

    model_config = ConfigDict(frozen=True)

    snapshot: EngineSnapshot
    speed: float


class SimulationRunner:
    def __init__(
        self,
        log_root: Path,
        config: WarehouseConfig | None = None,
        seed: int = 0,
        speed: float = 1.0,
    ) -> None:
        self._log_root = log_root
        self._config = config or default_config()
        self._speed = _checked_speed(speed)
        self._listeners: list[Callable[[RunnerState], None]] = []
        self._last_notified: RunnerState | None = None
        self._session = 0
        self._engine = self._new_engine(seed)

    def state(self) -> RunnerState:
        return RunnerState(snapshot=self._engine.snapshot(), speed=self._speed)

    def subscribe(self, listener: Callable[[RunnerState], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def step(self) -> None:
        """Advance one tick (or apply a queued pause/resume/end)."""
        self._engine.advance(1)

    def pause(self) -> None:
        """Pause now; applied at once, without waiting for the next paced tick."""
        self._submit("pause")
        self.step()
        self._notify()

    def resume(self) -> None:
        """Resume a paused Run now; the resuming step also advances one tick."""
        if self._engine.snapshot().status != "paused":
            return
        self._submit("resume")
        self.step()
        self._notify()

    def set_speed(self, speed: float) -> None:
        self._speed = _checked_speed(speed)
        self._notify()

    def reset(self, seed: int) -> None:
        """End the current Run and start a fresh one from `seed`."""
        new_engine = self._new_engine(seed)  # first, so a failure keeps the old Run
        self._submit("end")
        self._engine.advance(1)
        self._engine = new_engine
        self._notify()

    async def run(self, sleep: Sleep = asyncio.sleep) -> None:
        """Tick forever at the configured pace, notifying subscribers."""
        while True:
            self.step()
            self._notify()
            await sleep(1.0 / (BASE_TICKS_PER_SECOND * self._speed))

    def _submit(self, kind: str) -> None:
        tick = self._engine.snapshot().tick
        self._engine.submit(Command(tick=tick, type=kind))

    def _new_engine(self, seed: int) -> Engine:
        # Each Run gets its own session directory: the same seed derives the same
        # run_id (ADR-0005), and the file log refuses to reuse one within a root.
        self._session += 1
        while (session_root := self._log_root / f"session-{self._session:04d}").exists():
            self._session += 1
        publisher = FileEventPublisher(session_root)
        return Engine.create(self._config, seed=seed, publisher=publisher)

    def _notify(self) -> None:
        if not self._listeners:
            return
        state = self.state()
        if state == self._last_notified:
            return
        self._last_notified = state
        for listener in list(self._listeners):
            listener(state)


def _checked_speed(speed: float) -> float:
    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise ValueError(f"speed must be between {MIN_SPEED} and {MAX_SPEED}, got {speed}")
    return float(speed)
