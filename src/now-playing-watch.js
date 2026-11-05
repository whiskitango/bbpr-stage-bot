// Asks AzuraCast what is on air every so often and reports when the song
// changes, so the Stage topic and the bot's status can follow along. A failed
// check is skipped quietly; the music doesn't depend on it.

const { LiveActs } = require('./live-acts');

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

  // "Artist - Title" normally; "DJ Whiski - Title" while a DJ is live, with
  // the DJ's name spelled as in LiveActs. A DJ whose software sends no song
  // details, or only their own name, shows as just their name.
  static songOf(body, acts = new LiveActs()) {
    const song = (body && body.now_playing && body.now_playing.song) || {};
    const raw = body && body.live && body.live.is_live && body.live.streamer_name;
    if (raw && raw.trim()) {
      const dj = acts.nameOf(raw);
      const title = song.title || song.text || '';
      return title && !acts.same(title, dj) ? `${dj} - ${title}` : dj;
    }
    return song.artist && song.title ? `${song.artist} - ${song.title}` : (song.text || '');
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
