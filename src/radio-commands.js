// The /radio command: join, leave and status.
//
// Who may use it is Discord's job, not this file's. The command is registered
// as needing Manage Channels, so Discord hides it from everyone else and
// refuses it if they try. A server owner can change that under Server
// Settings -> Integrations (for example, a "Radio" role only); checking
// Manage Channels again here would undo that choice. It works only inside
// servers, never in DMs, and its replies are seen only by whoever used it.

const {
  SlashCommandBuilder, PermissionFlagsBits, ChannelType, InteractionContextType, MessageFlags,
} = require('discord.js');

const NEEDED = [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.Connect, PermissionFlagsBits.Speak];
// What being a Stage moderator gives: start the Stage and speak without asking.
const MODERATOR = [PermissionFlagsBits.ManageChannels, PermissionFlagsBits.MuteMembers, PermissionFlagsBits.MoveMembers];

const NAMES = {
  [PermissionFlagsBits.ViewChannel]: 'View Channel',
  [PermissionFlagsBits.Connect]: 'Connect',
  [PermissionFlagsBits.Speak]: 'Speak',
  [PermissionFlagsBits.ManageChannels]: 'Manage Channels',
  [PermissionFlagsBits.MuteMembers]: 'Mute Members',
  [PermissionFlagsBits.MoveMembers]: 'Move Members',
};

class RadioCommands {
  constructor({ fleet, allowed, station = 'the radio', log = console } = {}) {
    this.fleet = fleet;
    this.allowed = allowed;
    this.station = station;
    this.log = log;
  }

  static definition(station = 'the radio') {
    return new SlashCommandBuilder()
      .setName('radio')
      .setDescription(`Play ${station} on a Stage`)
      .setDefaultMemberPermissions(PermissionFlagsBits.ManageChannels)
      .setContexts(InteractionContextType.Guild)
      .addSubcommand((s) => s.setName('join').setDescription('Play the station in a Stage or voice channel')
        .addChannelOption((o) => o.setName('channel').setDescription('Where to play (default: the channel you are in)')
          .addChannelTypes(ChannelType.GuildStageVoice, ChannelType.GuildVoice)))
      .addSubcommand((s) => s.setName('leave').setDescription('Stop playing on this server'))
      .addSubcommand((s) => s.setName('status').setDescription('Where the station is playing on this server'));
  }

  // Names of permissions the bot lacks in a channel.
  static missing(permissions, wanted) {
    if (!permissions) return wanted.map((p) => NAMES[p]);
    return wanted.filter((p) => !permissions.has(p)).map((p) => NAMES[p]);
  }

  async register(application) {
    await application.commands.set([RadioCommands.definition(this.station).toJSON()]);
    this.log.info('[commands] /radio registered');
  }

  async handle(interaction) {
    if (!interaction.isChatInputCommand() || interaction.commandName !== 'radio') return;
    const reply = (content) => (interaction.deferred || interaction.replied
      ? interaction.editReply({ content })
      : interaction.reply({ content, flags: MessageFlags.Ephemeral }));
    try {
      if (!interaction.inGuild()) return await reply('This only works in a server.');
      if (!this.allowed.allows(interaction.guildId)) {
        this.log.warn(`[commands] refused /radio in a server not on the list: ${interaction.guildId}`);
        return await reply('This bot isn\'t set up to play on this server.');
      }
      const sub = interaction.options.getSubcommand();
      this.log.info(`[commands] /radio ${sub} by ${interaction.user.tag} in ${interaction.guild ? interaction.guild.name : interaction.guildId}`);
      if (sub === 'join') return await this.join(interaction, reply);
      if (sub === 'leave') return await reply(this.fleet.leave(interaction.guildId) ? 'Stopped. The bot has left.' : 'It isn\'t playing on this server.');
      if (sub === 'status') return await reply(this.status(interaction.guildId));
    } catch (err) {
      this.log.warn(`[commands] ${err.message}`);
      await reply(`Something went wrong: ${err.message}`).catch(() => {});
    }
  }

  async join(interaction, reply) {
    const channel = interaction.options.getChannel('channel')
      || (interaction.member && interaction.member.voice && interaction.member.voice.channel);
    if (!channel) return reply('Join a Stage first, or pick one: `/radio join channel:`');

    const me = interaction.guild.members.me;
    const perms = channel.permissionsFor(me);
    const lacking = RadioCommands.missing(perms, NEEDED);
    if (lacking.length) return reply(`The bot needs ${lacking.join(', ')} in ${channel}.`);

    await interaction.deferReply({ flags: MessageFlags.Ephemeral });
    await this.fleet.join(interaction.guildId, channel.id);
    const isStage = channel.type === ChannelType.GuildStageVoice;
    const notModerator = isStage && RadioCommands.missing(perms, MODERATOR).length > 0;
    return reply(notModerator
      ? `Playing in ${channel}. The bot isn't a Stage moderator here, so a moderator has to invite it to speak. Make it a Stage moderator in the channel's permissions to skip that.`
      : `Playing ${this.station} in ${channel}.`);
  }

  status(guildId) {
    const presence = this.fleet.get(guildId);
    if (!presence) return 'Not playing on this server. Use `/radio join`.';
    return presence.channel ? `Playing in <#${presence.channelId}>.` : `Trying to get into <#${presence.channelId}>.`;
  }
}

module.exports = { RadioCommands };
