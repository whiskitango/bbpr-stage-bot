"""Reopens the station's stream on a schedule (STREAM_REFRESH_HOURS), as a
precaution against a connection that has gone wrong in a way nothing else
notices. Only the stream is reopened: the bot stays in every channel, and
listeners hear a gap of about a second. Off (0) unless set."""

from __future__ import annotations

import time
from typing import Callable


class StreamRefresh:
    def __init__(self, hours: float = 0, now: Callable[[], float] = time.monotonic):
        self.interval_s = max(0.0, float(hours)) * 3600
        self.now = now
        self.opened_at = now()

    @classmethod
    def parse(cls, text: str) -> 'StreamRefresh':
        """Reads "2" or "1.5"; anything else, or nothing, is off."""
        try:
            return cls(float((text or '').strip() or 0))
        except ValueError:
            return cls()

    @property
    def on(self) -> bool:
        return self.interval_s > 0

    @property
    def hours(self) -> float:
        return self.interval_s / 3600

    def opened(self) -> None:
        self.opened_at = self.now()

    def due(self) -> bool:
        return self.on and self.now() - self.opened_at >= self.interval_s
