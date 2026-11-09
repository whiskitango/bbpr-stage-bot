"""Everything the bot needs to know, read once from the environment (or the
.env file at the top of the repo). Kept in one place so a missing setting is
reported up front, by name."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Mapping, Optional

from .volume import Volume

ROOT = Path(__file__).resolve().parents[2]
STREAM_DEFAULT = 'https://radio.octowow.st/listen/booty_bay_pirate_radio/radio.mp3'
NOW_PLAYING_DEFAULT = 'https://radio.octowow.st/api/nowplaying/booty_bay_pirate_radio'
TOPIC_DEFAULT = 'Booty Bay Pirate Radio'
DATA_DEFAULT = ROOT / 'data'
STATUS_HOST_DEFAULT = '127.0.0.1'
STATUS_TOKEN_MIN = 24


def id_list(text: str) -> List[str]:
    return [part for part in re.split(r'[\s,]+', text or '') if part]


class Config:
    def __init__(self, token: str = '', stage_channel_ids: Optional[List[str]] = None,
                 allowed_guild_ids: Optional[List[str]] = None, stream_url: str = STREAM_DEFAULT,
                 now_playing_url: str = NOW_PLAYING_DEFAULT, topic: str = TOPIC_DEFAULT,
                 bitrate: int = 128, data_dir: Path = DATA_DEFAULT, voice_debug: bool = False,
                 status_port: int = 0, status_host: str = STATUS_HOST_DEFAULT, status_token: str = '',
                 status_tls_cert: str = '', status_tls_key: str = '', station: str = '',
                 volume: Optional[Volume] = None):
        self.token = token
        self.stage_channel_ids = stage_channel_ids or []   # joined at start, besides saved ones
        self.allowed_guild_ids = allowed_guild_ids or []   # empty: any server the bot is in
        self.stream_url = stream_url
        self.now_playing_url = now_playing_url             # '' turns the song in the bot's status off
        self.topic = topic
        self.bitrate = bitrate                             # kbps sent to Discord
        self.volume = volume or Volume()                   # % of the station's level
        self.data_dir = Path(data_dir)
        self.voice_debug = voice_debug
        self.status_port = status_port                     # 0: no status page (see status_server.py)
        self.status_host = status_host
        self.status_token = status_token
        self.status_tls_cert = status_tls_cert
        self.status_tls_key = status_tls_key
        self.station_name = station                        # '' : taken from the stream address

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
        try:
            status_port = int(pick('STATUS_PORT', '0') or 0)
        except ValueError:
            status_port = 0
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
            status_port=status_port,
            status_host=pick('STATUS_HOST', '') or STATUS_HOST_DEFAULT,
            status_token=pick('STATUS_TOKEN', ''),
            status_tls_cert=pick('STATUS_TLS_CERT', ''),
            status_tls_key=pick('STATUS_TLS_KEY', ''),
            station=pick('STATION', ''),
            volume=Volume.parse(pick('VOLUME', '')),
        )

    @property
    def station(self) -> str:
        """The station's short name, which radio-metrics matches its counts by:
        STATION if set, otherwise the part after /listen/ in the stream address."""
        if self.station_name:
            return self.station_name
        found = re.search(r'/listen/([^/]+)/', self.stream_url or '')
        return found.group(1) if found else ''

    @property
    def channels_file(self) -> Path:
        return self.data_dir / 'channels.json'

    @property
    def log_folder(self) -> Path:
        return self.data_dir / 'logs'

    def missing(self) -> List[str]:
        """Names of required settings that are missing; empty when ready."""
        need = {'DISCORD_TOKEN': self.token, 'STREAM_URL': self.stream_url}
        if self.status_port:
            # Long enough that guessing it over the network is hopeless.
            need[f'STATUS_TOKEN (at least {STATUS_TOKEN_MIN} characters)'] = len(self.status_token) >= STATUS_TOKEN_MIN
            if bool(self.status_tls_cert) != bool(self.status_tls_key):
                need['STATUS_TLS_CERT and STATUS_TLS_KEY (both, or neither)'] = False
        return [name for name, value in need.items() if not value]
