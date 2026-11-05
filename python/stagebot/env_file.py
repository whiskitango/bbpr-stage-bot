"""Reads a .env file into the environment, without overriding anything
already set there. Lines are NAME=value; blank lines and # comments are
skipped, and surrounding quotes are dropped."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, MutableMapping, Optional


class EnvFile:
    def __init__(self, path: Path):
        self.path = Path(path)

    @staticmethod
    def parse(text: str) -> Dict[str, str]:
        values: Dict[str, str] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
                value = value[1:-1]
            values[name.strip()] = value
        return values

    def load(self, env: Optional[MutableMapping[str, str]] = None) -> bool:
        env = os.environ if env is None else env
        if not self.path.exists():
            return False
        for name, value in self.parse(self.path.read_text(encoding='utf-8')).items():
            env.setdefault(name, value)
        return True
