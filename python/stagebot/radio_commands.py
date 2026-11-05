"""The /radio command: join, leave and status.

Who may use it is Discord's job, not this file's. The command is registered
as needing Manage Channels, so Discord hides it from everyone else and refuses
it if they try. A server owner can change that under Server Settings ->
Integrations; checking Manage Channels again here would undo that choice. It
works only inside servers, and its replies are seen only by whoever used it."""

from __future__ import annotations

import logging
from typing import List, Optional, Union

import discord
from discord import app_commands

from .allowed_servers import AllowedServers
from .stage_fleet import StageFleet

log = logging.getLogger('stagebot')

NEEDED = ('view_channel', 'connect', 'speak')
MODERATOR = ('manage_channels', 'mute_members', 'move_members')
NAMES = {
    'view_channel': 'View Channel', 'connect': 'Connect', 'speak': 'Speak',
    'manage_channels': 'Manage Channels', 'mute_members': 'Mute Members', 'move_members': 'Move Members',
}


class RadioCommands(app_commands.Group):
    def __init__(self, fleet: StageFleet, allowed: AllowedServers, station: str = 'the radio'):
        super().__init__(
            name='radio', description=f'Play {station} on a Stage',
            default_permissions=discord.Permissions(manage_channels=True), guild_only=True,
        )
        self.fleet = fleet
        self.allowed = allowed
        self.station = station

    @staticmethod
    def missing(permissions: Optional[discord.Permissions], wanted) -> List[str]:
        if permissions is None:
            return [NAMES[p] for p in wanted]
        return [NAMES[p] for p in wanted if not getattr(permissions, p)]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id is None:
            await interaction.response.send_message('This only works in a server.', ephemeral=True)
            return False
        if not self.allowed.allows(interaction.guild_id):
            log.warning(f'[commands] refused /radio in a server not on the list: {interaction.guild_id}')
            await interaction.response.send_message("This bot isn't set up to play on this server.", ephemeral=True)
            return False
        sub = interaction.command.name if interaction.command else '?'
        where = interaction.guild.name if interaction.guild else interaction.guild_id
        log.info(f'[commands] /radio {sub} by {interaction.user} in {where}')
        return True

    async def on_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        if isinstance(error, app_commands.CheckFailure):
            return                    # interaction_check already told them why
        err = getattr(error, 'original', error)
        log.warning(f'[commands] {err!r}')
        text = f'Something went wrong: {err}'
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(content=text)
            else:
                await interaction.response.send_message(text, ephemeral=True)
        except discord.HTTPException:
            pass

    @app_commands.command(name='join', description='Play the station in a Stage or voice channel')
    @app_commands.describe(channel='Where to play (default: the channel you are in)')
    async def join(self, interaction: discord.Interaction,
                   channel: Optional[Union[discord.StageChannel, discord.VoiceChannel]] = None) -> None:
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        channel = channel or (member.voice.channel if member and member.voice else None)
        if channel is None:
            await interaction.response.send_message('Join a Stage first, or pick one: `/radio join channel:`', ephemeral=True)
            return
        perms = channel.permissions_for(interaction.guild.me)
        lacking = self.missing(perms, NEEDED)
        if lacking:
            await interaction.response.send_message(f"The bot needs {', '.join(lacking)} in {channel.mention}.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.fleet.join(interaction.guild_id, channel.id)
        not_moderator = isinstance(channel, discord.StageChannel) and self.missing(perms, MODERATOR)
        await interaction.edit_original_response(content=(
            f"Playing in {channel.mention}. The bot isn't a Stage moderator here, so a moderator has to invite "
            "it to speak. Make it a Stage moderator in the channel's permissions to skip that."
            if not_moderator else f'Playing {self.station} in {channel.mention}.'
        ))

    @app_commands.command(name='leave', description='Stop playing on this server')
    async def leave(self, interaction: discord.Interaction) -> None:
        left = await self.fleet.leave(interaction.guild_id)
        await interaction.response.send_message(
            'Stopped. The bot has left.' if left else "It isn't playing on this server.", ephemeral=True)

    @app_commands.command(name='status', description='Where the station is playing on this server')
    async def status(self, interaction: discord.Interaction) -> None:
        presence = self.fleet.get(interaction.guild_id)
        if not presence:
            text = 'Not playing on this server. Use `/radio join`.'
        elif presence.voice and presence.voice.is_connected():
            text = f'Playing in <#{presence.channel_id}>.'
        else:
            text = f'Trying to get into <#{presence.channel_id}>.'
        await interaction.response.send_message(text, ephemeral=True)
