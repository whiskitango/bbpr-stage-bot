"""Every server the bot plays in, at once. All of them hear the same radio
stream, so the station is streamed (and counted by AzuraCast) once however
many servers listen. The fleet keeps one StagePresence per server, in step
with the ChannelStore."""

from __future__ import annotations

import asyncio
from typing import Callable, Dict, Optional

import discord

from .channel_store import ChannelStore
from .radio_stream import RadioStream
from .stage_presence import StagePresence


class StageFleet:
    def __init__(self, client: discord.Client, stream: RadioStream, topic: str, store: ChannelStore,
                 voice_debug: bool = False, make_presence: Callable[..., StagePresence] = StagePresence):
        self.client = client
        self.stream = stream
        self.topic = topic
        self.store = store
        self.voice_debug = voice_debug
        self.make_presence = make_presence
        self.by_guild: Dict[str, StagePresence] = {}

    def open(self, guild_id: str, channel_id: str) -> StagePresence:
        guild_id = str(guild_id)
        presence: Optional[StagePresence] = None

        def gone(p: StagePresence) -> None:
            self.forget(guild_id, p)

        presence = self.make_presence(self.client, int(channel_id), self.stream, self.topic,
                                      on_gone=gone, voice_debug=self.voice_debug)
        self.by_guild[guild_id] = presence
        return presence

    def start_all(self) -> None:
        """Rejoin every saved channel, as on startup."""
        for guild_id, channel_id in self.store.all():
            asyncio.create_task(self.open(guild_id, channel_id).start())

    async def join(self, guild_id, channel_id) -> StagePresence:
        """Move to a channel on a server, replacing any channel there. Returns
        once the bot is in it; raises (and keeps nothing) if it can't get in."""
        guild_id = str(guild_id)
        await self.leave(guild_id, keep_saved=True)
        presence = self.open(guild_id, channel_id)
        try:
            await presence.join()
        except Exception:
            await presence.leave()
            self.by_guild.pop(guild_id, None)
            raise
        self.store.set(guild_id, str(channel_id))
        return presence

    async def leave(self, guild_id, keep_saved: bool = False) -> bool:
        guild_id = str(guild_id)
        presence = self.by_guild.pop(guild_id, None)
        if presence:
            await presence.leave()
        if not keep_saved:
            self.store.remove(guild_id)
        return presence is not None

    def forget(self, guild_id: str, presence: StagePresence) -> None:
        if self.by_guild.get(guild_id) is not presence:
            return
        self.by_guild.pop(guild_id, None)
        self.store.remove(guild_id)

    def get(self, guild_id) -> Optional[StagePresence]:
        return self.by_guild.get(str(guild_id))

    async def on_own_voice_state(self, guild_id, after: discord.VoiceState) -> None:
        presence = self.get(guild_id)
        if presence:
            await presence.on_own_voice_state(after)

    async def leave_all(self) -> None:
        """Leave every channel but keep them saved, for the next start."""
        await asyncio.gather(*(p.leave() for p in list(self.by_guild.values())))
