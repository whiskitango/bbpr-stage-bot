// Keeps the station playing. The audio player goes idle whenever the stream
// ends (the server restarted, or the network dropped for longer than ffmpeg's
// reconnect covers), and this opens it again after a backoff, forever.

const { createAudioPlayer, AudioPlayerStatus, NoSubscriberBehavior } = require('@discordjs/voice');
const { Backoff } = require('./backoff');

class RadioPlayer {
  constructor({
    source, backoff = new Backoff(), log = console,
    timers = { setTimeout, clearTimeout },
    player = createAudioPlayer({ behaviors: { noSubscriber: NoSubscriberBehavior.Play } }),
  } = {}) {
    this.source = source;
    this.backoff = backoff;
    this.log = log;
    this.timers = timers;
    this.timer = null;
    this.stopped = false;
    // Play (not Pause) keeps the stream flowing while the bot is between
    // connections, so a reconnect picks up live audio, not a stale buffer.
    this.player = player;
    this.player.on(AudioPlayerStatus.Idle, () => this.retry());
    this.player.on('error', (err) => this.log.warn(`[player] ${err.message}`));
  }

  start() {
    this.stopped = false;
    this.play();
  }

  play() {
    this.timer = null;
    if (this.stopped) return;
    this.log.info('[player] opening the stream');
    this.backoff.started();
    this.player.play(this.source.open());
  }

  retry() {
    if (this.stopped || this.timer) return;
    const wait = this.backoff.next();
    this.log.warn(`[player] stream ended; reopening in ${Math.round(wait / 1000)} s`);
    this.timer = this.timers.setTimeout(() => this.play(), wait);
  }

  stop() {
    this.stopped = true;
    if (this.timer) this.timers.clearTimeout(this.timer);
    this.timer = null;
    this.player.stop(true);
    this.source.close();
  }
}

module.exports = { RadioPlayer };
