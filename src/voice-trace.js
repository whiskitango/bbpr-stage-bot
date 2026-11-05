// A window into the voice side, for when the bot looks connected but nobody
// hears it. Turned on with VOICE_DEBUG=1, it logs every state change of the
// audio player and of each voice connection (including the DAVE encryption
// handshake), and every 15 s how much audio has been played. Off, it does
// nothing.

class VoiceTrace {
  constructor({ enabled = false, log = console, every = 15000, timers = { setInterval, clearInterval } } = {}) {
    this.enabled = enabled;
    this.log = log;
    this.every = every;
    this.timers = timers;
    this.timer = null;
  }

  watchPlayer(player) {
    if (!this.enabled) return;
    player.on('stateChange', (from, to) => this.log.info(`[voice] player ${from.status} -> ${to.status}`));
    this.timer = this.timers.setInterval(() => this.report(player), this.every);
    if (this.timer.unref) this.timer.unref();
  }

  report(player) {
    const { status, resource } = player.state;
    const played = resource ? Math.round(resource.playbackDuration / 1000) : 0;
    const subs = player.playable ? player.playable.length : 0;
    this.log.info(`[voice] player ${status}, ${played} s played, ${subs} connection(s) ready to send`);
  }

  // The DAVE encryption state of a connection: protocol version, session
  // status (0 inactive, 1 pending, 2 awaiting response, 3 active) and whether
  // frames are being end-to-end encrypted.
  static daveOf(conn) {
    const net = conn.state && conn.state.networking;
    const dave = net && net.state && net.state.dave;
    if (!dave) return 'no DAVE';
    const s = dave.session;
    return `DAVE v${dave.protocolVersion}, status ${s ? s.status : '-'}, ready ${s ? s.ready : false}`;
  }

  watchConnection(conn, label) {
    if (!this.enabled) return;
    const timer = this.timers.setInterval(() => {
      if (conn.state.status === 'destroyed') { this.timers.clearInterval(timer); return; }
      this.log.info(`[voice] ${label}: ${VoiceTrace.daveOf(conn)}`);
    }, this.every);
    if (timer.unref) timer.unref();
    conn.on('stateChange', (from, to) => this.log.info(`[voice] ${label}: ${from.status} -> ${to.status}`));
    conn.on('debug', (msg) => this.log.info(`[voice] ${label}: ${msg}`));
  }

  stop() {
    if (this.timer) this.timers.clearInterval(this.timer);
    this.timer = null;
  }
}

module.exports = { VoiceTrace };
