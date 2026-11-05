// Which Discord servers the bot will play in. Anyone can invite a public bot
// to a server of their own, where they are the admin and so may use /radio.
// With ALLOWED_GUILD_IDS set, the bot refuses every other server; empty means
// any server it has been invited to (fine once "Public Bot" is off in the
// developer portal, so only you can invite it).

class AllowedServers {
  constructor(ids = []) {
    this.ids = new Set(ids.filter(Boolean));
  }

  static parse(text = '') {
    return new AllowedServers(String(text).split(/[\s,]+/));
  }

  get open() { return this.ids.size === 0; }

  allows(guildId) { return this.open || this.ids.has(guildId); }
}

module.exports = { AllowedServers };
