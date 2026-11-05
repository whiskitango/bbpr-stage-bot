// Which channel the bot plays in on each server, saved so a restart goes back
// to all of them. One channel per server: joining another channel on the same
// server replaces the first.

const fs = require('node:fs');
const path = require('node:path');

class ChannelStore {
  constructor({ file, fsys = fs, log = console } = {}) {
    this.file = file;
    this.fs = fsys;
    this.log = log;
    this.byGuild = new Map();
  }

  load() {
    try {
      const saved = JSON.parse(this.fs.readFileSync(this.file, 'utf8'));
      for (const [guildId, channelId] of Object.entries(saved)) this.byGuild.set(guildId, String(channelId));
    } catch (err) {
      if (err.code !== 'ENOENT') this.log.warn(`[channels] could not read ${this.file}: ${err.message}`);
    }
    return this;
  }

  all() { return [...this.byGuild.entries()].map(([guildId, channelId]) => ({ guildId, channelId })); }

  get(guildId) { return this.byGuild.get(guildId) || null; }

  set(guildId, channelId) {
    this.byGuild.set(guildId, channelId);
    this.save();
  }

  remove(guildId) {
    if (this.byGuild.delete(guildId)) this.save();
  }

  save() {
    const tmp = `${this.file}.tmp`;
    this.fs.mkdirSync(path.dirname(this.file), { recursive: true });
    this.fs.writeFileSync(tmp, JSON.stringify(Object.fromEntries(this.byGuild), null, 2));
    this.fs.renameSync(tmp, this.file);
  }
}

module.exports = { ChannelStore };
