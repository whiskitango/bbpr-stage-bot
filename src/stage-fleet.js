// Every server the bot plays in, at once. All of them hear the same audio
// player, so the station is streamed (and counted by AzuraCast) once however
// many servers listen. The fleet keeps one StagePresence per server, in step
// with the ChannelStore.

const { StagePresence } = require('./stage-presence');

class StageFleet {
  constructor({ client, player, topic, store, log = console, makePresence = (opts) => new StagePresence(opts) } = {}) {
    this.client = client;
    this.player = player;
    this.topic = topic;
    this.store = store;
    this.log = log;
    this.makePresence = makePresence;
    this.byGuild = new Map();
    this.currentTopic = '';
  }

  // Rejoin every saved channel, as on startup.
  startAll() {
    for (const { guildId, channelId } of this.store.all()) this.open(guildId, channelId).start();
  }

  open(guildId, channelId) {
    const presence = this.makePresence({
      client: this.client, channelId, player: this.player, topic: this.topic, log: this.log,
      onGone: () => this.forget(guildId, presence),
    });
    if (this.currentTopic) presence.wantedTopic = this.currentTopic;
    this.byGuild.set(guildId, presence);
    return presence;
  }

  // Move to a channel on a server, replacing any channel there. Resolves once
  // the bot is in it; rejects (and keeps nothing) if it can't get in.
  async join(guildId, channelId) {
    this.leave(guildId);
    const presence = this.open(guildId, channelId);
    try {
      await presence.join();
    } catch (err) {
      presence.leave();
      this.byGuild.delete(guildId);
      throw err;
    }
    this.store.set(guildId, channelId);
    return presence;
  }

  leave(guildId) {
    const presence = this.byGuild.get(guildId);
    if (presence) presence.leave();
    this.byGuild.delete(guildId);
    this.store.remove(guildId);
    return Boolean(presence);
  }

  forget(guildId, presence) {
    if (this.byGuild.get(guildId) !== presence) return;
    this.byGuild.delete(guildId);
    this.store.remove(guildId);
  }

  get(guildId) { return this.byGuild.get(guildId) || null; }

  get size() { return this.byGuild.size; }

  onOwnVoiceState(state) {
    const presence = this.byGuild.get(state.guild.id);
    if (presence) presence.onOwnVoiceState(state);
  }

  async setTopic(text) {
    this.currentTopic = text;
    await Promise.all([...this.byGuild.values()].map((p) => p.setTopic(text)));
  }

  leaveAll() {
    for (const presence of this.byGuild.values()) presence.leave();
  }
}

module.exports = { StageFleet };
