"""Only one copy of the bot at a time, Node or Python. Two copies log in as the
same bot and keep pushing each other off the voice channel. A small file holds
the running copy's process id (the same file the Node bot uses); a second copy
that finds it alive refuses to start, and one left by a crash is taken over."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

LOCK_FILE = Path(tempfile.gettempdir()) / 'bbpr-stage-bot.pid'


class ProcessCheck:
    """Whether a process id is still running. On Windows, os.kill(pid, 0)
    would end the process, so it asks the system instead."""

    @staticmethod
    def alive(pid: int) -> bool:
        if pid <= 0:
            return False
        if os.name == 'nt':
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not handle:
                return False
            code = ctypes.c_ulong()
            try:
                kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
                return code.value == 259  # STILL_ACTIVE
            finally:
                kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except OSError:
            return False


class InstanceLock:
    def __init__(self, file: Path = LOCK_FILE, pid: Optional[int] = None, check=ProcessCheck):
        self.file = Path(file)
        self.pid = pid or os.getpid()
        self.check = check
        self.held = False

    def acquire(self) -> Optional[int]:
        """The pid of the copy already running, or None once this copy holds the lock."""
        try:
            other = int(self.file.read_text().strip() or 0)
        except (OSError, ValueError):
            other = 0
        if other and other != self.pid and self.check.alive(other):
            return other
        self.file.write_text(str(self.pid))
        self.held = True
        return None

    def release(self) -> None:
        if not self.held:
            return
        try:
            if int(self.file.read_text().strip() or 0) == self.pid:
                self.file.unlink()
        except (OSError, ValueError):
            pass
        self.held = False
