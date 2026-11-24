"""The pure, deterministic warehouse engine."""

import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict

from warehouse_twin.commands import Command
from warehouse_twin.config import WarehouseConfig
from warehouse_twin.events import (
    Event,
    LocationSnapshot,
    LocationSnapshotPayload,
    ProductSnapshot,
    ProductSnapshotPayload,
    RobotSnapshot,
    RobotSnapshotPayload,
    RunEnded,
    RunEndedPayload,
    RunPaused,
    RunPausedPayload,
    RunResumed,
    RunResumedPayload,
    RunStarted,
    RunStartedPayload,
)
from warehouse_twin.publisher import EventPublisher


RunStatus = Literal["running", "paused", "ended"]


class EngineSnapshot(BaseModel):
    """Read-only view of the Run's current state."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    seed: int
    tick: int
    simulated_time: datetime
    status: RunStatus
    last_sequence: int
    config: WarehouseConfig


class Engine:
    def __init__(
        self,
        config: WarehouseConfig,
        seed: int,
        run_id: str,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._config = config
        self._publisher = publisher
        self._seed = seed
        self._run_id = run_id
        self._tick = 0
        self._status: RunStatus = "running"
        self._events: list[Event] = []
        self._pending: list[Command] = []

    @classmethod
    def create(
        cls,
        config: WarehouseConfig,
        seed: int,
        run_id: str | None = None,
        publisher: EventPublisher | None = None,
    ) -> Self:
        engine = cls(config, seed, run_id or _derive_run_id(config, seed), publisher)
        engine._emit_run_start()
        return engine

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    def submit(self, command: Command) -> None:
        """Queue a command to be applied when the Run reaches `command.tick`."""
        if command.tick < self._tick:
            raise ValueError(
                f"command tick {command.tick} is before current tick {self._tick}"
            )
        self._pending.append(command)

    def advance(self, ticks: int) -> None:
        """Step the Run `ticks` times; time stands still while paused or ended."""
        for _ in range(ticks):
            if self._status == "ended":
                return
            self._apply_due_commands()
            if self._status == "running":
                self._tick += 1

    def snapshot(self) -> EngineSnapshot:
        return EngineSnapshot(
            run_id=self._run_id,
            seed=self._seed,
            tick=self._tick,
            simulated_time=self._simulated_time(),
            status=self._status,
            last_sequence=len(self._events),
            config=self._config,
        )

    def _apply_due_commands(self) -> None:
        due = [c for c in self._pending if c.tick == self._tick]
        self._pending = [c for c in self._pending if c.tick != self._tick]
        for command in due:
            if self._status == "ended":
                break
            if command.type == "pause" and self._status == "running":
                self._status = "paused"
                self._emit(RunPaused, self._run_id, RunPausedPayload())
            elif command.type == "resume" and self._status == "paused":
                self._status = "running"
                self._emit(RunResumed, self._run_id, RunResumedPayload())
            elif command.type == "end":
                self._status = "ended"
                self._emit(RunEnded, self._run_id, RunEndedPayload(final_tick=self._tick))

    def _emit_run_start(self) -> None:
        config = self._config
        self._emit(RunStarted, self._run_id, RunStartedPayload(seed=self._seed, config=config))
        for product in config.products:
            self._emit(
                ProductSnapshot,
                product.sku,
                ProductSnapshotPayload(sku=product.sku, name=product.name),
            )
        for robot in config.robots:
            self._emit(
                RobotSnapshot,
                robot.robot_id,
                RobotSnapshotPayload(
                    robot_id=robot.robot_id,
                    x=robot.x,
                    y=robot.y,
                    load_capacity=robot.load_capacity,
                ),
            )
        for aisle in config.aisles:
            self._emit_location(
                aisle.aisle_id, "aisle", aisle.x, aisle.y, aisle.width, aisle.height
            )
        for slot in config.shelf_slots:
            self._emit_location(slot.slot_id, "shelf_slot", slot.x, slot.y, sku=slot.sku)
        for station in config.stations:
            self._emit_location(station.station_id, station.kind, station.x, station.y)

    def _emit_location(
        self,
        location_id: str,
        location_type: Any,
        x: int,
        y: int,
        width: int = 1,
        height: int = 1,
        sku: str | None = None,
    ) -> None:
        self._emit(
            LocationSnapshot,
            location_id,
            LocationSnapshotPayload(
                location_id=location_id,
                location_type=location_type,
                x=x,
                y=y,
                width=width,
                height=height,
                sku=sku,
            ),
        )

    def _simulated_time(self) -> datetime:
        return self._config.start_time + timedelta(
            seconds=self._tick * self._config.tick_seconds
        )

    def _emit(self, event_cls: type[Any], entity_id: str, payload: BaseModel) -> None:
        sequence = len(self._events) + 1
        event: Event = (
            event_cls(
                event_id=str(uuid.uuid5(uuid.UUID(self._run_id), str(sequence))),
                event_time=self._simulated_time(),
                simulation_tick=self._tick,
                sequence=sequence,
                run_id=self._run_id,
                entity_id=entity_id,
                payload=payload,
            )
        )
        self._events.append(event)
        if self._publisher is not None:
            self._publisher.publish(event)


def _derive_run_id(config: WarehouseConfig, seed: int) -> str:
    canonical = json.dumps(
        {"seed": seed, "config": json.loads(config.model_dump_json())}, sort_keys=True
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, canonical))
