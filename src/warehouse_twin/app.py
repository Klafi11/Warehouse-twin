"""FastAPI layer: runs the tick loop, takes controls over HTTP, streams state over WebSocket."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal, Self

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

from warehouse_twin.runner import MAX_SPEED, MIN_SPEED, RunnerState, SimulationRunner

STATIC_DIR = Path(__file__).parent / "static"


# Handlers are `async` so they mutate the runner on the event loop, like its tick loop.
class ControlRequest(BaseModel):
    action: Literal["pause", "resume", "speed", "reset"]
    speed: float | None = Field(default=None, ge=MIN_SPEED, le=MAX_SPEED)
    seed: int | None = None

    @model_validator(mode="after")
    def _has_what_the_action_needs(self) -> Self:
        if self.action == "speed" and self.speed is None:
            raise ValueError("speed is required for the speed action")
        if self.action == "reset" and self.seed is None:
            raise ValueError("seed is required for the reset action")
        return self


def _log_if_failed(task: "asyncio.Task[None]") -> None:
    if not task.cancelled() and (error := task.exception()) is not None:
        logging.getLogger(__name__).error("tick loop died", exc_info=error)


def create_app(log_root: Path, seed: int = 0, speed: float = 1.0) -> FastAPI:
    runner = SimulationRunner(log_root, seed=seed, speed=speed)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(runner.run())
        task.add_done_callback(_log_if_failed)
        try:
            yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Warehouse Twin", lifespan=lifespan)

    @app.get("/api/state")
    async def get_state() -> RunnerState:
        return runner.state()

    @app.post("/api/control")
    async def control(request: ControlRequest) -> RunnerState:
        match request.action:
            case "pause":
                runner.pause()
            case "resume":
                runner.resume()
            case "speed":
                assert request.speed is not None
                runner.set_speed(request.speed)
            case "reset":
                assert request.seed is not None
                runner.reset(request.seed)
        return runner.state()

    @app.websocket("/ws")
    async def stream(websocket: WebSocket) -> None:
        await websocket.accept()
        # Only the latest state matters to a viewer, so a slow client skips ahead.
        latest: asyncio.Queue[RunnerState] = asyncio.Queue(maxsize=1)

        def offer(state: RunnerState) -> None:
            if latest.full():
                latest.get_nowait()
            latest.put_nowait(state)

        unsubscribe = runner.subscribe(offer)
        async def send_updates() -> None:
            while True:
                state = await latest.get()
                await websocket.send_text(state.model_dump_json())

        async def watch_for_disconnect() -> None:
            with contextlib.suppress(WebSocketDisconnect):
                while True:
                    await websocket.receive_text()

        tasks = [
            asyncio.create_task(send_updates()),
            asyncio.create_task(watch_for_disconnect()),
        ]
        try:
            offer(runner.state())
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            unsubscribe()
            for task in tasks:
                task.cancel()

    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app
