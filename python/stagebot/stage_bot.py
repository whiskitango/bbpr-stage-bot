"""The bot as a whole: log in to Discord, keep the station's stream playing,
keep a seat on every server's Stage it was asked to join, answer /radio, and
show the song on air as its "Listening to" status. The Stage topic stays
the station's name: changing it posts a notice in the Stage chat each song.
With STATUS_PORT set, it also serves how many people are listening, for
radio-metrics (status_server.py)."""

from __future__ import annotations

import logging

import discord
from discord import app_commands

from .allowed_servers import AllowedServers
from .channel_store import ChannelStore
from .config import Config
from .ffmpeg_locator import FfmpegLocator
from .now_playing import NowPlayingWatch
from .radio_commands import RadioCommands
from .radio_stream import RadioStream
from .stage_fleet import StageFleet
from .status_report import StatusReport
from .status_server import StatusServer

log = logging.getLogger('stagebot')


class StageBot(discord.Client):
    def __init__(self, config: Config, ffmpeg: str = ''):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.voice_states = True
        super().__init__(intents=intents)
        self.config = config
        self.stream = RadioStream(config.stream_url, ffmpeg or FfmpegLocator.find(), config.bitrate,
                                  volume=config.volume, refresh=config.stream_refresh)
        self.store = ChannelStore(config.channels_file).load()
        self.allowed = AllowedServers(config.allowed_guild_ids)
        self.fleet = StageFleet(self, self.stream, config.topic, self.store, voice_debug=config.voice_debug)
        self.tree = app_commands.CommandTree(self)
        self.tree.add_command(RadioCommands(self.fleet, self.allowed, config.topic))
        self.watch = NowPlayingWatch(config.now_playing_url, self.on_song)
        self.status_page = StatusServer(
            config.status_host, config.status_port, config.status_token,
            StatusReport(self, self.fleet, config.station).build,
            tls_cert=config.status_tls_cert, tls_key=config.status_tls_key,
        ) if config.status_port else None
        self.started = False

    async def setup_hook(self) -> None:
        if self.status_page:
            await self.status_page.start()
        try:
            await self.tree.sync()
            log.info('[commands] /radio registered')
        except discord.HTTPException as err:
            log.error(f'[commands] could not register /radio: {err}')

    async def on_ready(self) -> None:
        log.info(f'[discord] logged in as {self.user}')
        if self.started:          # on_ready fires again after a gateway reconnect
            return
        self.started = True
        if self.allowed.open:
            log.warning('[discord] ALLOWED_GUILD_IDS is empty: /radio works on any server the bot is invited to')
        self.stream.start()
        await self.adopt_configured()
        self.fleet.start_all()
        self.watch.start()

    async def adopt_configured(self) -> None:
        """Channels named in STAGE_CHANNEL_ID count as joined, unless /radio has
        since picked another channel on that server."""
        for channel_id in self.config.stage_channel_ids:
            try:
                channel = self.get_channel(int(channel_id)) or await self.fetch_channel(int(channel_id))
            except (ValueError, discord.HTTPException) as err:
                log.warning(f'[stage] STAGE_CHANNEL_ID {channel_id}: {err}')
                continue
            guild = getattr(channel, 'guild', None)
            if not guild:
                continue
            if not self.allowed.allows(guild.id):
                log.warning(f'[stage] {channel_id} is on a server not in ALLOWED_GUILD_IDS')
                continue
            if not self.store.get(str(guild.id)):
                self.store.set(str(guild.id), str(channel_id))
        for guild_id, _ in self.store.all():
            if not self.allowed.allows(guild_id):
                self.store.remove(guild_id)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState,
                                    after: discord.VoiceState) -> None:
        if self.user and member.id == self.user.id:
            await self.fleet.on_own_voice_state(member.guild.id, after)

    async def on_guild_remove(self, guild: discord.Guild) -> None:
        await self.fleet.leave(guild.id)

    async def on_song(self, song: str) -> None:
        log.info(f'[now playing] {song}')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=song[:128]))

    async def shutdown(self) -> None:
        log.info('Leaving the Stage...')
        self.watch.stop()
        if self.status_page:
            await self.status_page.stop()
        await self.fleet.leave_all()
        self.stream.stop()
        await self.close()
