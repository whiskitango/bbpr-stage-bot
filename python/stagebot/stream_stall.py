"""Notices when the station's stream has gone quiet without ending.

A connection that stalls (still open, nothing arriving) doesn't end ffmpeg,
so nothing is logged and every server hears silence while the bot otherwise
looks fine. RadioStream marks each packet here, and a watcher reopens the
stream once nothing has come for LIMIT_S seconds. The limit allows for the
second or so a fresh connection takes to start, and comes before ffmpeg's own
read timeout (FfmpegCommand.READ_TIMEOUT_S), so a stall is always logged."""

from __future__ import annotations

import time
from typing import Callable


class StreamStall:
    LIMIT_S = 10.0

    def __init__(self, limit: float = LIMIT_S, now: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.now = now
        self.last = now()

    def reset(self) -> None:
        """The stream was (re)opened: the wait starts now."""
        self.last = self.now()

    def fed(self) -> None:
        self.last = self.now()

    def quiet_for(self) -> float:
        return self.now() - self.last

    def stalled(self) -> bool:
        return self.quiet_for() >= self.limit
