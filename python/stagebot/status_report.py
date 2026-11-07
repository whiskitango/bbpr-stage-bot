"""What the status page says: for each channel the bot plays in, whether it is
playing and how many people are in there, plus a total. The total counts
only the channels where the station is actually playing, because people in a
Stage the bot hasn't reached yet aren't hearing the station.

"servers" is how many servers have the bot installed, playing or not, so a
reader can see how far it has spread beyond the servers it plays in.

The station's short name is included so a reader (radio-metrics) can tell
which station the counts belong to."""

from __future__ import annotations

import time
from typing import Callable

import discord

from .stage_audience import StageAudience


class StatusReport:
    def __init__(self, client: discord.Client, fleet, station: str, clock: Callable[[], float] = time.time):
        self.client = client
        self.fleet = fleet
        self.station = station
        self.clock = clock

    def bot_id(self):
        return self.client.user.id if self.client.user else None

    def channel(self, presence) -> dict:
        # The cached channel has the latest voice states; the one the presence
        # holds may be older.
        channel = self.client.get_channel(presence.channel_id) or presence.channel
        voice = presence.voice
        playing = bool(presence.ready and voice and voice.is_connected())
        guild = getattr(channel, 'guild', None)
        return {
            'server': guild.name if guild else '',
            'channel': getattr(channel, 'name', '') or str(presence.channel_id),
            'kind': 'stage' if isinstance(channel, discord.StageChannel) else 'voice',
            'playing': playing,
            'listeners': StageAudience.count(channel, self.bot_id()),
        }

    def build(self) -> dict:
        channels = [self.channel(p) for p in self.fleet.presences()]
        return {
            'station': self.station,
            'at': int(self.clock() * 1000),
            'listeners': sum(c['listeners'] for c in channels if c['playing']),
            'servers': len(self.client.guilds),
            'channels': channels,
        }
