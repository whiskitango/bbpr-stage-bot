// Asks AzuraCast what is on air every so often and reports when the song
// changes, so the Stage topic and the bot's status can follow along. A failed
// check is skipped quietly; the music doesn't depend on it.

class NowPlayingWatch {
  constructor({ url, onChange, every = 30000, fetcher = fetch, log = console, timers = { setInterval, clearInterval } } = {}) {
    this.url = url;
    this.onChange = onChange;
    this.every = every;
    this.fetcher = fetcher;
    this.log = log;
    this.timers = timers;
    this.last = null;
    this.timer = null;
  }

  static songOf(body) {
    const song = body && body.now_playing && body.now_playing.song;
    if (!song) return '';
    const text = song.artist && song.title ? `${song.artist} - ${song.title}` : (song.text || '');
    const dj = body.live && body.live.is_live && body.live.streamer_name;
    return dj ? `LIVE: ${dj} | ${text}` : text;
  }

  start() {
    if (!this.url) return;
    this.check();
    this.timer = this.timers.setInterval(() => this.check(), this.every);
  }

  async check() {
    try {
      const res = await this.fetcher(this.url, { headers: { 'User-Agent': 'bbpr-stage-bot' } });
      if (!res.ok) return;
      const song = NowPlayingWatch.songOf(await res.json());
      if (!song || song === this.last) return;
      this.last = song;
      await this.onChange(song);
    } catch (err) {
      this.log.warn(`[now playing] ${err.message}`);
    }
  }

  stop() {
    if (this.timer) this.timers.clearInterval(this.timer);
    this.timer = null;
  }
}

module.exports = { NowPlayingWatch };
