import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from warehouse_twin.app import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    # speed 100 keeps the real-time loop quick; the app is otherwise as launched.
    with TestClient(create_app(tmp_path, seed=3, speed=100)) as client:
        yield client


def test_state_exposes_the_static_layout_from_the_engine_snapshot(client: TestClient) -> None:
    state = client.get("/api/state").json()

    config = state["snapshot"]["config"]
    assert (config["width"], config["height"]) == (12, 8)
    kinds = {s["kind"] for s in config["stations"]}
    assert kinds == {"packing", "inbound_dock", "back_room", "charger", "repair_bay"}
    assert len(config["aisles"]) == 2
    assert len(config["shelf_slots"]) == 4
    assert state["snapshot"]["seed"] == 3


def test_seam_2_posted_command_reaches_engine_ws_streams_state_and_logs_are_written(
    client: TestClient, tmp_path: Path
) -> None:
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["snapshot"]["status"] == "running"

        assert client.post("/api/control", json={"action": "pause"}).status_code == 200

        status = first["snapshot"]["status"]
        while status != "paused":  # ticks may arrive first; state streams until paused
            status = ws.receive_json()["snapshot"]["status"]

    assert client.get("/api/state").json()["snapshot"]["status"] == "paused"
    log = next(tmp_path.glob("*/*/runs.events.jsonl"))
    types = [json.loads(line)["event_type"] for line in log.read_text().splitlines()]
    assert types == ["run_started", "run_paused"]


def test_resume_speed_and_reset_controls(client: TestClient) -> None:
    client.post("/api/control", json={"action": "pause"})
    resumed = client.post("/api/control", json={"action": "resume"}).json()
    assert resumed["snapshot"]["status"] == "running"

    sped = client.post("/api/control", json={"action": "speed", "speed": 4}).json()
    assert sped["speed"] == 4

    reset = client.post("/api/control", json={"action": "reset", "seed": 99}).json()
    assert reset["snapshot"]["seed"] == 99
    assert reset["snapshot"]["status"] == "running"
    assert reset["snapshot"]["tick"] < 50


@pytest.mark.parametrize(
    "body",
    [
        {"action": "explode"},
        {"action": "speed"},
        {"action": "speed", "speed": 0},
        {"action": "reset"},
    ],
)
def test_invalid_controls_are_rejected(client: TestClient, body: dict[str, object]) -> None:
    assert client.post("/api/control", json=body).status_code == 422


def test_index_page_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "<canvas" in response.text
