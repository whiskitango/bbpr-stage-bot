// Turns the station's stream URL into audio Discord can play. ffmpeg reads the
// MP3 stream and re-encodes it to Opus in an Ogg container, which the voice
// library sends as it is, so Node needs no Opus encoder. ffmpeg's own
// reconnect flags ride out short network blips without a gap on the Stage.

const { spawn } = require('node:child_process');
const { createAudioResource, StreamType } = require('@discordjs/voice');

class StreamSource {
  constructor({ url, ffmpeg = 'ffmpeg', bitrate = 128, log = console, spawner = spawn } = {}) {
    this.url = url;
    this.ffmpeg = ffmpeg;
    this.bitrate = bitrate;
    this.log = log;
    this.spawner = spawner;
    this.proc = null;
  }

  static args(url, bitrate) {
    return [
      '-hide_banner', '-loglevel', 'error',
      '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_on_network_error', '1', '-reconnect_delay_max', '5',
      '-i', url,
      '-vn', '-c:a', 'libopus', '-b:a', `${bitrate}k`, '-ar', '48000', '-ac', '2',
      '-f', 'ogg', 'pipe:1',
    ];
  }

  // A fresh resource each time; the previous ffmpeg is stopped first.
  open() {
    this.close();
    const proc = this.spawner(this.ffmpeg, StreamSource.args(this.url, this.bitrate), { stdio: ['ignore', 'pipe', 'pipe'] });
    proc.stderr.on('data', (d) => this.log.warn(`[ffmpeg] ${String(d).trim()}`));
    proc.on('error', (err) => this.log.error(`[ffmpeg] could not start ${this.ffmpeg}: ${err.message}`));
    this.proc = proc;
    return createAudioResource(proc.stdout, { inputType: StreamType.OggOpus });
  }

  close() {
    if (this.proc && this.proc.exitCode === null) this.proc.kill('SIGKILL');
    this.proc = null;
  }
}

module.exports = { StreamSource };
