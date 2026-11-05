"""Which channel the bot plays in on each server, saved so a restart goes back
to all of them. One channel per server. Same file format as the Node bot's
data/channels.json, so either can pick up where the other left off."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

log = logging.getLogger('stagebot')


class ChannelStore:
    def __init__(self, file: Path):
        self.file = Path(file)
        self.by_guild: Dict[str, str] = {}

    def load(self) -> 'ChannelStore':
        try:
            saved = json.loads(self.file.read_text(encoding='utf-8'))
            self.by_guild = {str(g): str(c) for g, c in saved.items()}
        except FileNotFoundError:
            pass
        except (OSError, ValueError, AttributeError) as err:
            log.warning(f'[channels] could not read {self.file}: {err}')
        return self

    def all(self) -> List[Tuple[str, str]]:
        return list(self.by_guild.items())

    def get(self, guild_id: str) -> Optional[str]:
        return self.by_guild.get(str(guild_id))

    def set(self, guild_id: str, channel_id: str) -> None:
        self.by_guild[str(guild_id)] = str(channel_id)
        self.save()

    def remove(self, guild_id: str) -> None:
        if self.by_guild.pop(str(guild_id), None) is not None:
            self.save()

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(self.file.suffix + '.tmp')
        tmp.write_text(json.dumps(self.by_guild, indent=2), encoding='utf-8')
        os.replace(tmp, self.file)
