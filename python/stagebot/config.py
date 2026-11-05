"""Everything the bot needs to know, read once from the environment (or the
.env file at the top of the repo). Kept in one place so a missing setting is
reported up front, by name."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Mapping, Optional

ROOT = Path(__file__).resolve().parents[2]
STREAM_DEFAULT = 'https://radio.octowow.st/listen/booty_bay_pirate_radio/radio.mp3'
NOW_PLAYING_DEFAULT = 'https://radio.octowow.st/api/nowplaying/booty_bay_pirate_radio'
TOPIC_DEFAULT = 'Booty Bay Pirate Radio'
DATA_DEFAULT = ROOT / 'data'


def id_list(text: str) -> List[str]:
    return [part for part in re.split(r'[\s,]+', text or '') if part]


class Config:
    def __init__(self, token: str = '', stage_channel_ids: Optional[List[str]] = None,
                 allowed_guild_ids: Optional[List[str]] = None, stream_url: str = STREAM_DEFAULT,
                 now_playing_url: str = NOW_PLAYING_DEFAULT, topic: str = TOPIC_DEFAULT,
                 bitrate: int = 128, data_dir: Path = DATA_DEFAULT, voice_debug: bool = False):
        self.token = token
        self.stage_channel_ids = stage_channel_ids or []   # joined at start, besides saved ones
        self.allowed_guild_ids = allowed_guild_ids or []   # empty: any server the bot is in
        self.stream_url = stream_url
        self.now_playing_url = now_playing_url             # '' turns the song in the bot's status off
        self.topic = topic
        self.bitrate = bitrate                             # kbps sent to Discord
        self.data_dir = Path(data_dir)
        self.voice_debug = voice_debug

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> 'Config':
        env = os.environ if env is None else env

        def pick(name: str, fallback: str) -> str:
            value = env.get(name)
            return fallback if value is None else value.strip()

        try:
            bitrate = int(pick('BITRATE', '128')) or 128
        except ValueError:
            bitrate = 128
        return cls(
            token=pick('DISCORD_TOKEN', ''),
            stage_channel_ids=id_list(pick('STAGE_CHANNEL_ID', '')),
            allowed_guild_ids=id_list(pick('ALLOWED_GUILD_IDS', '')),
            stream_url=pick('STREAM_URL', STREAM_DEFAULT),
            now_playing_url=pick('NOW_PLAYING_URL', NOW_PLAYING_DEFAULT),
            topic=pick('STAGE_TOPIC', TOPIC_DEFAULT),
            bitrate=bitrate,
            data_dir=Path(pick('DATA_DIR', '') or DATA_DEFAULT),
            voice_debug=pick('VOICE_DEBUG', '').lower() in ('1', 'true', 'yes'),
        )

    @property
    def channels_file(self) -> Path:
        return self.data_dir / 'channels.json'

    def missing(self) -> List[str]:
        """Names of required settings that are missing; empty when ready."""
        need = {'DISCORD_TOKEN': self.token, 'STREAM_URL': self.stream_url}
        return [name for name, value in need.items() if not value]
