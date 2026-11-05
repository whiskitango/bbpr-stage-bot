"""The bot's place on one server's Stage: join the channel, open the Stage if
nobody has, step up from the audience to speaker, start playing, and get back
there after a network drop, a Discord restart or being moved to the audience.
A plain voice channel works too; there the bot just joins and plays.

Becoming a speaker makes Discord move the bot to another voice server. If
that happens while the voice connection is still being set up, the bot can
end up sending audio that never reaches the audience. So the bot always lets
the connection settle first, then steps up, then lets the move finish before
it plays. If it arrives already marked as a speaker (after a restart), it
steps down to the audience first so it goes through that same path.

Speaking on a Stage needs the bot to be a Stage moderator. Without that it
asks to speak, and a moderator has to accept it by hand.

If the channel is deleted or the bot loses access to it, retrying forever
helps nobody: on_gone is called and the fleet forgets the channel."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Optional

import discord

from .connection_health import ConnectionHealth
from .radio_stream import RadioListener, RadioStream

log = logging.getLogger('stagebot')

REJOIN_S = 15
CHECK_S = 15
SPEAK_RETRY_S = 30
SETTLE_S = 3        # let a fresh connection, or a speaker move, finish


class ChannelGone(Exception):
    pass


class StagePresence:
    def __init__(self, client: discord.Client, channel_id: int, stream: RadioStream, topic: str,
                 on_gone: Callable[['StagePresence'], None] = lambda p: None, voice_debug: bool = False):
        self.client = client
        self.channel_id = int(channel_id)
        self.stream = stream
        self.topic = topic
        self.on_gone = on_gone
        self.voice_debug = voice_debug
        self.channel: Optional[discord.abc.GuildChannel] = None
        self.voice: Optional[discord.VoiceClient] = None
        self.listener: Optional[RadioListener] = None
        self.watchdog: Optional[asyncio.Task] = None
        self.joining = asyncio.Lock()
        self.ready = False            # connected, settled and (on a Stage) stepped up
        self.leaving = False
        self.refused_at = 0.0
        self.health = ConnectionHealth()

    @property
    def is_stage(self) -> bool:
        return isinstance(self.channel, discord.StageChannel)

    @property
    def label(self) -> str:
        return f'{self.channel.guild.name} / {self.channel.name}' if self.channel else str(self.channel_id)

    async def fetch_channel(self):
        channel = self.client.get_channel(self.channel_id)
        if channel is None:
            try:
                channel = await self.client.fetch_channel(self.channel_id)
            except (discord.NotFound, discord.Forbidden) as err:
                raise ChannelGone(f'channel {self.channel_id}: {err}')
        if not isinstance(channel, (discord.StageChannel, discord.VoiceChannel)):
            raise ChannelGone(f'channel {self.channel_id} is not a Stage or voice channel')
        return channel

    async def join(self) -> None:
        async with self.joining:      # a rejoin and /radio join never run at once
            await self.connect_and_play()
        if not self.watchdog and not self.leaving:
            self.watchdog = asyncio.create_task(self.keep_alive())

    async def connect_and_play(self) -> None:
        self.leaving = False
        self.ready = False
        self.channel = await self.fetch_channel()
        existing = self.channel.guild.voice_client
        if existing:                  # start clean: a half-dead connection only gets in the way
            await existing.disconnect(force=True)
        self.voice = await self.channel.connect(
            timeout=30, reconnect=True, self_deaf=not self.is_stage, self_mute=False)
        if self.leaving:
            await self.disconnect()
            return
        log.info(f"[stage] joined {self.label}{'' if self.is_stage else ' (a voice channel, not a Stage)'}")
        if self.is_stage:
            await asyncio.sleep(SETTLE_S)
            await self.open_stage()
            await self.step_down_if_speaker()
            if await self.speak():
                await asyncio.sleep(SETTLE_S)   # let Discord's move to a speaker server finish
        if self.leaving:
            return
        self.play()
        self.ready = True

    def play(self) -> None:
        if not self.voice or not self.voice.is_connected() or self.voice.is_playing():
            return
        self.listener = self.stream.listen()
        self.voice.play(self.listener, after=lambda err: err and log.warning(f'[player] {self.label}: {err}'))

    async def start(self) -> None:
        """Join, and keep trying if it fails for a reason that may pass."""
        try:
            await self.join()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            await self.failed(err)

    async def failed(self, err: Exception) -> None:
        if isinstance(err, ChannelGone):
            log.warning(f'[stage] giving up on {self.label}: {err}')
            await self.leave()
            self.on_gone(self)
            return
        log.warning(f'[stage] {self.label}: {err!r}')
        await self.disconnect()
        if not self.leaving:
            log.warning(f'[stage] lost {self.label}; rejoining in {REJOIN_S} s')
            await asyncio.sleep(REJOIN_S)
            if not self.leaving:
                await self.start()

    async def keep_alive(self) -> None:
        """Every so often: still connected, still playing? Fix whichever isn't."""
        while not self.leaving:
            await asyncio.sleep(CHECK_S)
            if self.leaving:
                break
            if self.joining.locked():
                continue              # a join is under way
            try:
                connected = bool(self.voice and self.voice.is_connected())
                given_up = self.voice is None or self.channel.guild.voice_client is None
                if self.health.needs_rejoin(connected, given_up):
                    log.warning(f'[stage] not connected to {self.label}; rejoining')
                    async with self.joining:
                        await self.disconnect()
                        await self.connect_and_play()
                    continue
                if not connected:
                    continue          # discord.py is reconnecting; give it time
                if self.is_stage and self.ready:
                    await self.speak()    # still in the audience? try again
                self.play()
                if self.voice_debug:
                    self.report()
            except asyncio.CancelledError:
                raise
            except ChannelGone as err:    # deleted, or access lost: stop for good
                self.watchdog = None
                await self.failed(err)
                return
            except Exception as err:
                log.warning(f'[stage] {self.label}: {err!r}')

    def report(self) -> None:
        state = self.voice._connection
        dave = state.dave_session
        listener = self.listener
        log.info(
            f'[voice] {self.label}: playing {self.voice.is_playing()}, '
            f'{listener.packets if listener else 0} packets sent, {listener.silent if listener else 0} silent, '
            f'endpoint {state.endpoint}, DAVE v{state.dave_protocol_version}, ready {bool(dave and dave.ready)}'
        )

    async def open_stage(self) -> None:
        """Start the Stage with the station's topic if it isn't live already."""
        if self.channel.instance:
            return
        try:
            await self.channel.create_instance(topic=self.topic)
            log.info(f'[stage] started the Stage in {self.label}')
        except discord.HTTPException as err:
            log.warning(f'[stage] could not start the Stage in {self.label} (make the bot a Stage moderator): {err}')

    def my_voice(self) -> Optional[discord.VoiceState]:
        me = self.channel.guild.me
        voice = me.voice if me else None
        return voice if voice and voice.channel and voice.channel.id == self.channel_id else None

    async def step_down_if_speaker(self) -> None:
        """Arrived already on stage (Discord remembered it): go to the audience
        first, so stepping up moves the bot to a speaker server like normal."""
        voice = self.my_voice()
        if not voice or voice.suppress:
            return
        try:
            await self.channel.guild.me.edit(suppress=True)
            log.info(f'[stage] arrived as a speaker in {self.label}; stepping down first')
            await asyncio.sleep(SETTLE_S)
        except discord.HTTPException as err:
            log.warning(f'[stage] could not step down in {self.label}: {err}')

    async def speak(self) -> bool:
        """Step up to speaker. True if the bot just became one."""
        voice = self.my_voice()
        if not voice or not voice.suppress:
            return False
        # Asking to speak changes the bot's voice state; after a refusal, wait
        # before trying again.
        now = time.monotonic()
        if now - self.refused_at < SPEAK_RETRY_S:
            return False
        me = self.channel.guild.me
        try:
            await me.edit(suppress=False)
            self.refused_at = 0.0
            log.info(f'[stage] speaking in {self.label}')
            return True
        except discord.HTTPException as err:
            self.refused_at = now
            log.warning(f'[stage] could not become a speaker in {self.label}, asking to speak instead '
                        f'(make the bot a Stage moderator): {err}')
            try:
                await me.request_to_speak()
            except discord.HTTPException:
                pass
            return False

    async def on_own_voice_state(self, after: discord.VoiceState) -> None:
        """Moved back to the audience by someone: step up again, once settled.
        Ignored while joining, which does its own stepping up."""
        if not self.ready or not self.is_stage or self.joining.locked():
            return
        if after.channel and after.channel.id == self.channel_id and after.suppress:
            await asyncio.sleep(SETTLE_S)
            await self.speak()

    async def disconnect(self) -> None:
        self.ready = False
        voice, self.voice = self.voice, None
        if voice:
            try:
                await voice.disconnect(force=True)
            except Exception:
                pass

    async def leave(self) -> None:
        self.leaving = True
        task, self.watchdog = self.watchdog, None
        if task and task is not asyncio.current_task():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await self.disconnect()
