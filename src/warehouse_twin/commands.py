"""Tick-stamped commands that drive the engine."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Command(BaseModel):
    """A request applied when the Run reaches `tick`; the command log is replayable."""

    model_config = ConfigDict(frozen=True)

    tick: int
    type: Literal["pause", "resume", "end"]
