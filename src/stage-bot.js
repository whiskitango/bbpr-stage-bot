// The bot as a whole: log in to Discord, keep the station's stream playing,
// keep a seat on every server's Stage it was asked to join, answer /radio,
// and show the song on air as the Stage topics and its "Listening to" status.

const { Client, GatewayIntentBits, Events, ActivityType } = require('discord.js');
const { StreamSource } = require('./stream-source');
const { RadioPlayer } = require('./radio-player');
const { StageFleet } = require('./stage-fleet');
const { ChannelStore } = require('./channel-store');
const { RadioCommands } = require('./radio-commands');
const { AllowedServers } = require('./allowed-servers');
const { NowPlayingWatch } = require('./now-playing-watch');
const { StageTopic } = require('./stage-topic');
const { FfmpegLocator } = require('./ffmpeg-locator');
const { VoiceTrace } = require('./voice-trace');

class StageBot {
  constructor({ config, log = console, ffmpeg = FfmpegLocator.find() } = {}) {
    this.config = config;
    this.log = log;
    this.client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildVoiceStates] });
    this.source = new StreamSource({ url: config.streamUrl, ffmpeg, bitrate: config.bitrate, log });
    this.radio = new RadioPlayer({ source: this.source, log });
    this.trace = new VoiceTrace({ enabled: config.voiceDebug, log });
    this.trace.watchPlayer(this.radio.player);
    this.store = new ChannelStore({ file: config.channelsFile, log }).load();
    this.allowed = new AllowedServers(config.allowedGuildIds);
    this.fleet = new StageFleet({ client: this.client, player: this.radio.player, topic: config.topic, store: this.store, log, trace: this.trace });
    this.commands = new RadioCommands({ fleet: this.fleet, allowed: this.allowed, station: config.topic, log });
    this.watch = new NowPlayingWatch({ url: config.nowPlayingUrl, onChange: (song) => this.onSong(song), log });

    this.client.once(Events.ClientReady, () => this.ready());
    this.client.on(Events.InteractionCreate, (i) => this.commands.handle(i));
    this.client.on(Events.VoiceStateUpdate, (old, now) => {
      if (now.id === this.client.user.id) this.fleet.onOwnVoiceState(now, old);
    });
    // Removed from a server: stop trying to play there.
    this.client.on(Events.GuildDelete, (guild) => this.fleet.leave(guild.id));
    this.client.on(Events.Error, (err) => this.log.warn(`[discord] ${err.message}`));
  }

  async start() {
    await this.client.login(this.config.token);
  }

  async ready() {
    this.log.info(`[discord] logged in as ${this.client.user.tag}`);
    if (this.allowed.open) this.log.warn('[discord] ALLOWED_GUILD_IDS is empty: /radio works on any server the bot is invited to');
    this.radio.start();
    try { await this.commands.register(this.client.application); } catch (err) {
      this.log.error(`[commands] could not register /radio: ${err.message}`);
    }
    await this.adoptConfigured();
    this.fleet.startAll();
    this.watch.start();
  }

  // Channels named in STAGE_CHANNEL_ID count as joined, unless /radio has
  // since picked another channel on that server.
  async adoptConfigured() {
    for (const id of this.config.stageChannelIds) {
      try {
        const channel = await this.client.channels.fetch(id);
        if (!channel || !channel.guild) continue;
        if (!this.allowed.allows(channel.guild.id)) { this.log.warn(`[stage] ${id} is on a server not in ALLOWED_GUILD_IDS`); continue; }
        if (!this.store.get(channel.guild.id)) this.store.set(channel.guild.id, id);
      } catch (err) {
        this.log.warn(`[stage] STAGE_CHANNEL_ID ${id}: ${err.message}`);
      }
    }
    // Saved channels on servers since removed from the allowed list are dropped.
    for (const { guildId } of this.store.all()) if (!this.allowed.allows(guildId)) this.store.remove(guildId);
  }

  async onSong(song) {
    this.log.info(`[now playing] ${song}`);
    this.client.user.setActivity(song.slice(0, 128), { type: ActivityType.Listening });
    await this.fleet.setTopic(StageTopic.format(this.config.topic, song));
  }

  async stop() {
    this.watch.stop();
    this.trace.stop();
    this.fleet.leaveAll();
    this.radio.stop();
    await this.client.destroy();
  }
}

module.exports = { StageBot };
