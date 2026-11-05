// Finds the ffmpeg to decode the stream with. FFMPEG_PATH wins; then the copy
// ffmpeg-static downloads on install (handy on Windows); then whatever ffmpeg
// is on the PATH (the Docker image installs one).

const fs = require('node:fs');

class FfmpegLocator {
  static find({ env = process.env, exists = fs.existsSync, bundled = FfmpegLocator.bundled() } = {}) {
    if (env.FFMPEG_PATH) return env.FFMPEG_PATH;
    if (bundled && exists(bundled)) return bundled;
    return 'ffmpeg';
  }

  static bundled() {
    try { return require('ffmpeg-static'); } catch { return null; }
  }
}

module.exports = { FfmpegLocator };
