// Everything the bot needs to know, read once from the environment (or a
// .env file next to index.js). Kept in one place so a missing setting is
// reported up front, by name, instead of surfacing later as an odd Discord
// error.

const path = require('node:path');

const STREAM_DEFAULT = 'https://radio.octowow.st/listen/booty_bay_pirate_radio/radio.mp3';
const NOW_PLAYING_DEFAULT = 'https://radio.octowow.st/api/nowplaying/booty_bay_pirate_radio';
const DATA_DEFAULT = path.join(__dirname, '..', 'data');

const list = (text) => String(text || '').split(/[\s,]+/).filter(Boolean);

class Config {
  constructor({
    token = '', stageChannelIds = [], allowedGuildIds = [],
    streamUrl = STREAM_DEFAULT, nowPlayingUrl = NOW_PLAYING_DEFAULT,
    topic = 'Booty Bay Pirate Radio', bitrate = 128, dataDir = DATA_DEFAULT,
  } = {}) {
    this.token = token;
    this.stageChannelIds = stageChannelIds;   // channels to join at start, besides those /radio join saved
    this.allowedGuildIds = allowedGuildIds;   // empty: any server the bot is in
    this.streamUrl = streamUrl;
    this.nowPlayingUrl = nowPlayingUrl;       // '' turns the song-in-topic off
    this.topic = topic;
    this.bitrate = bitrate;                   // kbps sent to Discord
    this.dataDir = dataDir;
  }

  static fromEnv(env = process.env) {
    const pick = (name, fallback) => (env[name] === undefined ? fallback : env[name].trim());
    return new Config({
      token: pick('DISCORD_TOKEN', ''),
      stageChannelIds: list(pick('STAGE_CHANNEL_ID', '')),
      allowedGuildIds: list(pick('ALLOWED_GUILD_IDS', '')),
      streamUrl: pick('STREAM_URL', STREAM_DEFAULT),
      nowPlayingUrl: pick('NOW_PLAYING_URL', NOW_PLAYING_DEFAULT),
      topic: pick('STAGE_TOPIC', 'Booty Bay Pirate Radio'),
      bitrate: Number(pick('BITRATE', '128')) || 128,
      dataDir: pick('DATA_DIR', DATA_DEFAULT) || DATA_DEFAULT,
    });
  }

  get channelsFile() { return path.join(this.dataDir, 'channels.json'); }

  // The names of required settings that are missing; empty when ready to run.
  missing() {
    const need = { DISCORD_TOKEN: this.token, STREAM_URL: this.streamUrl };
    return Object.keys(need).filter((k) => !need[k]);
  }
}

module.exports = { Config };
