// The bot's place on one server's Stage: join the channel, open the Stage if
// nobody has, step up from the audience to speaker, and get back there after
// a network drop, a server restart or being moved to the audience. A plain
// voice channel works too (servers without Community can't have Stages);
// there the bot just joins and plays.
//
// Speaking on a Stage needs the bot to be a Stage moderator (or have Mute
// Members on the channel). Without that it asks to speak, and a moderator has
// to accept it by hand.
//
// If the channel is deleted or the bot loses access to it, retrying forever
// helps nobody: onGone is called and the fleet forgets the channel.

const { ChannelType } = require('discord.js');
const { joinVoiceChannel, entersState, VoiceConnectionStatus } = require('@discordjs/voice');

const READY_MS = 30000;
const RECOVER_MS = 5000;     // a drop that heals itself does so within this
const REJOIN_MS = 15000;
const GONE_CODES = new Set([10003, 50001]);   // Unknown Channel, Missing Access

class ChannelGone extends Error {}

class StagePresence {
  static TYPES = new Set([ChannelType.GuildStageVoice, ChannelType.GuildVoice]);

  constructor({
    client, channelId, player, topic, onGone = () => {}, log = console,
    timers = { setTimeout, clearTimeout },
  } = {}) {
    this.client = client;
    this.channelId = channelId;
    this.player = player;
    this.topic = topic;
    this.onGone = onGone;
    this.log = log;
    this.timers = timers;
    this.channel = null;
    this.isStage = false;
    this.connection = null;
    this.rejoinTimer = null;
    this.leaving = false;
    this.wantedTopic = '';
  }

  get label() {
    return this.channel ? `${this.channel.guild.name} / ${this.channel.name}` : this.channelId;
  }

  async fetchChannel() {
    let channel;
    try {
      channel = await this.client.channels.fetch(this.channelId);
    } catch (err) {
      if (GONE_CODES.has(err.code)) throw new ChannelGone(`channel ${this.channelId}: ${err.message}`);
      throw err;
    }
    if (!channel || !StagePresence.TYPES.has(channel.type)) {
      throw new ChannelGone(`channel ${this.channelId} is not a Stage or voice channel`);
    }
    return channel;
  }

  async join() {
    this.leaving = false;
    const channel = await this.fetchChannel();
    this.channel = channel;
    this.isStage = channel.type === ChannelType.GuildStageVoice;
    const conn = joinVoiceChannel({
      channelId: channel.id,
      guildId: channel.guild.id,
      adapterCreator: channel.guild.voiceAdapterCreator,
      selfDeaf: true,
    });
    this.connection = conn;
    conn.on(VoiceConnectionStatus.Disconnected, () => this.recover(conn));
    conn.on('error', (err) => this.log.warn(`[stage] ${this.label}: ${err.message}`));
    await entersState(conn, VoiceConnectionStatus.Ready, READY_MS);
    conn.subscribe(this.player);
    this.log.info(`[stage] joined ${this.label}${this.isStage ? '' : ' (a voice channel, not a Stage)'}`);
    if (!this.isStage) return;            // a voice channel has no stage, speakers or topic
    await this.openStage();
    await this.speak();
    if (this.wantedTopic) await this.setTopic(this.wantedTopic);
  }

  // Join, and keep trying if it fails for a reason that may pass.
  async start() {
    try {
      await this.join();
    } catch (err) {
      this.failed(err);
    }
  }

  failed(err) {
    if (this.connection) { this.connection.destroy(); this.connection = null; }
    if (err instanceof ChannelGone) {
      this.log.warn(`[stage] giving up on ${this.label}: ${err.message}`);
      this.leaving = true;
      this.onGone(this);
      return;
    }
    this.log.warn(`[stage] ${this.label}: ${err.message}`);
    this.rejoinLater();
  }

  // Start the Stage with the station's topic if it isn't already live.
  async openStage() {
    if (this.channel.stageInstance) return;
    try {
      await this.channel.createStageInstance({ topic: this.wantedTopic || this.topic });
      this.log.info(`[stage] started the Stage in ${this.label}`);
    } catch (err) {
      this.log.warn(`[stage] could not start the Stage in ${this.label} (make the bot a Stage moderator): ${err.message}`);
    }
  }

  async speak() {
    const me = this.channel && this.channel.guild.members.me;
    if (!me || me.voice.channelId !== this.channelId || !me.voice.suppress) return;
    try {
      await me.voice.setSuppressed(false);
      this.log.info(`[stage] speaking in ${this.label}`);
    } catch (err) {
      this.log.warn(`[stage] could not become a speaker in ${this.label}, asking to speak instead: ${err.message}`);
      await me.voice.setRequestToSpeak(true).catch(() => {});
    }
  }

  // The bot's own voice state changed: moved back to the audience, step up.
  onOwnVoiceState(state) {
    if (this.isStage && state.channelId === this.channelId && state.suppress) this.speak();
  }

  // Remembered, so a song that changes before the bot is on stage still
  // becomes the topic once it is.
  async setTopic(text) {
    this.wantedTopic = text;
    const stage = this.isStage && this.channel && this.channel.stageInstance;
    if (!stage || stage.topic === text) return;
    try { await stage.setTopic(text); } catch (err) { this.log.warn(`[stage] topic in ${this.label}: ${err.message}`); }
  }

  // A drop either heals itself (Discord moves the call to another server) or
  // it doesn't, and then the bot starts over.
  async recover(conn) {
    try {
      await Promise.race([
        entersState(conn, VoiceConnectionStatus.Signalling, RECOVER_MS),
        entersState(conn, VoiceConnectionStatus.Connecting, RECOVER_MS),
      ]);
    } catch {
      if (conn.state.status !== VoiceConnectionStatus.Destroyed) conn.destroy();
      if (this.connection === conn) this.connection = null;
      this.rejoinLater();
    }
  }

  rejoinLater() {
    if (this.leaving || this.rejoinTimer) return;
    this.log.warn(`[stage] lost ${this.label}; rejoining in ${REJOIN_MS / 1000} s`);
    this.rejoinTimer = this.timers.setTimeout(async () => {
      this.rejoinTimer = null;
      if (this.leaving) return;
      try { await this.join(); } catch (err) { this.failed(err); }
    }, REJOIN_MS);
  }

  leave() {
    this.leaving = true;
    if (this.rejoinTimer) this.timers.clearTimeout(this.rejoinTimer);
    this.rejoinTimer = null;
    if (this.connection) this.connection.destroy();
    this.connection = null;
  }
}

module.exports = { StagePresence, ChannelGone };
