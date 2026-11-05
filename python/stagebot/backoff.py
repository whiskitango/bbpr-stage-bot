"""How long to wait before reopening the stream: 2 s, then doubling to a
minute while it keeps failing. A stream that played for a while before ending
counts as healthy, so the next wait starts short again."""

from __future__ import annotations

import time
from typing import Callable, Optional


class Backoff:
    def __init__(self, first: float = 2.0, maximum: float = 60.0, healthy_after: float = 60.0,
                 now: Callable[[], float] = time.monotonic):
        self.first = first
        self.maximum = maximum
        self.healthy_after = healthy_after
        self.now = now
        self.delay = first
        self.started_at: Optional[float] = None

    def started(self) -> None:
        self.started_at = self.now()

    def next(self) -> float:
        if self.started_at is not None and self.now() - self.started_at >= self.healthy_after:
            self.delay = self.first
        wait = self.delay
        self.delay = min(self.delay * 2, self.maximum)
        self.started_at = None
        return wait
