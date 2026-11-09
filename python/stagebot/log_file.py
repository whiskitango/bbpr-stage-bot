"""Keeps the bot's log in a file as well as on the screen, so it is still there
after the container is rebuilt. Docker's own log goes with the container, and
"docker compose up --build" (or any .env change) makes a new one, so the
lines from when something went wrong are often gone by the time anyone looks.

The file sits in the data folder (a Docker volume on the server), with the
time on every line in UTC. It rotates: at MAX_BYTES it moves to .1, .1 to .2
and so on, keeping KEEP old files, so it can't fill the disk."""

from __future__ import annotations

import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class LogFile:
    NAME = 'stagebot.log'
    MAX_BYTES = 10_000_000
    KEEP = 5

    def __init__(self, folder: Path, max_bytes: int = MAX_BYTES, keep: int = KEEP):
        self.folder = Path(folder)
        self.max_bytes = max_bytes
        self.keep = keep
        self.handler: Optional[logging.Handler] = None

    @property
    def path(self) -> Path:
        return self.folder / self.NAME

    @staticmethod
    def formatter() -> logging.Formatter:
        stamped = logging.Formatter('%(asctime)s UTC %(levelname)-7s %(message)s', '%Y-%m-%d %H:%M:%S')
        stamped.converter = time.gmtime
        return stamped

    def attach(self, logger: Optional[logging.Logger] = None) -> bool:
        """Starts writing every INFO line and above to the file. False (and
        said on stderr) if the folder can't be written; the bot runs on."""
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(self.path, maxBytes=self.max_bytes, backupCount=self.keep,
                                          encoding='utf-8')
        except OSError as err:
            print(f'Could not keep a log file in {self.folder}: {err}', file=sys.stderr)
            return False
        # discord.py's debug chatter (VOICE_DEBUG) stays on the screen only.
        handler.setLevel(logging.INFO)
        handler.setFormatter(self.formatter())
        (logger or logging.getLogger()).addHandler(handler)
        self.handler = handler
        return True

    def detach(self, logger: Optional[logging.Logger] = None) -> None:
        if self.handler:
            (logger or logging.getLogger()).removeHandler(self.handler)
            self.handler.close()
            self.handler = None
