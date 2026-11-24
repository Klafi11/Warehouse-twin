"""Warehouse configuration: the map, catalog and robots a Run is built from."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Product(_Frozen):
    sku: str
    name: str


class Aisle(_Frozen):
    """A walkable rectangle of lane cells."""

    aisle_id: str
    x: int
    y: int
    width: int
    height: int


class ShelfSlot(_Frozen):
    slot_id: str
    x: int
    y: int
    sku: str


StationKind = Literal["packing", "inbound_dock", "back_room", "charger", "repair_bay"]


class Station(_Frozen):
    station_id: str
    kind: StationKind
    x: int
    y: int


class RobotSpec(_Frozen):
    robot_id: str
    x: int
    y: int
    load_capacity: int = 4


class WarehouseConfig(_Frozen):
    width: int
    height: int
    start_time: datetime
    tick_seconds: int = 1
    products: tuple[Product, ...]
    aisles: tuple[Aisle, ...]
    shelf_slots: tuple[ShelfSlot, ...]
    stations: tuple[Station, ...]
    robots: tuple[RobotSpec, ...]


def default_config() -> WarehouseConfig:
    """A small believable warehouse: two aisles, four products, two robots."""
    return WarehouseConfig(
        width=12,
        height=8,
        start_time=datetime(2026, 1, 1, 8, 0, 0, tzinfo=UTC),
        products=(
            Product(sku="SKU-001", name="Phone case"),
            Product(sku="SKU-002", name="USB cable"),
            Product(sku="SKU-003", name="Desk lamp"),
            Product(sku="SKU-004", name="Notebook"),
        ),
        aisles=(
            Aisle(aisle_id="A1", x=2, y=1, width=1, height=6),
            Aisle(aisle_id="A2", x=5, y=1, width=1, height=6),
        ),
        shelf_slots=(
            ShelfSlot(slot_id="S-A1-1", x=1, y=2, sku="SKU-001"),
            ShelfSlot(slot_id="S-A1-2", x=3, y=2, sku="SKU-002"),
            ShelfSlot(slot_id="S-A2-1", x=4, y=2, sku="SKU-003"),
            ShelfSlot(slot_id="S-A2-2", x=6, y=2, sku="SKU-004"),
        ),
        stations=(
            Station(station_id="PACK-1", kind="packing", x=10, y=1),
            Station(station_id="DOCK-1", kind="inbound_dock", x=10, y=6),
            Station(station_id="BACK-1", kind="back_room", x=11, y=6),
            Station(station_id="CHG-1", kind="charger", x=0, y=7),
            Station(station_id="REPAIR-1", kind="repair_bay", x=11, y=0),
        ),
        robots=(
            RobotSpec(robot_id="R1", x=9, y=1),
            RobotSpec(robot_id="R2", x=9, y=2),
        ),
    )
