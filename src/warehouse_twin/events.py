"""Business event contracts (ADR-0002 envelope, ADR-0003 Pydantic source of truth)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from warehouse_twin.config import StationKind, WarehouseConfig

SCHEMA_VERSION = 1


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class RunStartedPayload(_Frozen):
    seed: int
    config: WarehouseConfig


class ProductSnapshotPayload(_Frozen):
    sku: str
    name: str


class RobotSnapshotPayload(_Frozen):
    robot_id: str
    x: int
    y: int
    load_capacity: int


LocationType = Literal["aisle", "shelf_slot", StationKind]


class LocationSnapshotPayload(_Frozen):
    location_id: str
    location_type: LocationType
    x: int
    y: int
    width: int = 1
    height: int = 1
    sku: str | None = None


class _Envelope(_Frozen):
    event_id: str
    schema_version: int = SCHEMA_VERSION
    event_time: datetime
    simulation_tick: int
    sequence: int
    run_id: str
    entity_id: str


class RunStarted(_Envelope):
    event_type: Literal["run_started"] = "run_started"
    payload: RunStartedPayload


class ProductSnapshot(_Envelope):
    event_type: Literal["product_snapshot"] = "product_snapshot"
    payload: ProductSnapshotPayload


class RobotSnapshot(_Envelope):
    event_type: Literal["robot_snapshot"] = "robot_snapshot"
    payload: RobotSnapshotPayload


class LocationSnapshot(_Envelope):
    event_type: Literal["location_snapshot"] = "location_snapshot"
    payload: LocationSnapshotPayload


class RunPausedPayload(_Frozen):
    pass


class RunPaused(_Envelope):
    event_type: Literal["run_paused"] = "run_paused"
    payload: RunPausedPayload


class RunResumedPayload(_Frozen):
    pass


class RunResumed(_Envelope):
    event_type: Literal["run_resumed"] = "run_resumed"
    payload: RunResumedPayload


class RunEndedPayload(_Frozen):
    final_tick: int


class RunEnded(_Envelope):
    event_type: Literal["run_ended"] = "run_ended"
    payload: RunEndedPayload


Event = (
    RunStarted
    | ProductSnapshot
    | RobotSnapshot
    | LocationSnapshot
    | RunPaused
    | RunResumed
    | RunEnded
)
EventModel = Annotated[Event, Field(discriminator="event_type")]

_STREAM_BY_EVENT_TYPE = {
    "run_started": "runs.events",
    "run_paused": "runs.events",
    "run_resumed": "runs.events",
    "run_ended": "runs.events",
    "product_snapshot": "ref.products",
    "robot_snapshot": "ref.robots",
    "location_snapshot": "ref.locations",
}


def stream_for(event: Event) -> str:
    """The topic/stream an event is published to (ADR-0001, ADR-0004)."""
    return _STREAM_BY_EVENT_TYPE[event.event_type]
