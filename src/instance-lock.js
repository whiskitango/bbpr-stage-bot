// Only one copy of the bot at a time. Two copies log in as the same bot and
// keep pushing each other off the voice channel, so the audio drops every few
// seconds ("Cannot perform IP discovery - socket closed"). A small file holds
// the running copy's process id; a second copy that finds it alive refuses to
// start, and one left behind by a crash is taken over.

const fs = require('node:fs');

class InstanceLock {
  constructor({ file, pid = process.pid, alive = InstanceLock.alive, fsys = fs } = {}) {
    this.file = file;
    this.pid = pid;
    this.alive = alive;
    this.fs = fsys;
    this.held = false;
  }

  static alive(pid) {
    try { process.kill(pid, 0); return true; } catch (err) { return err.code === 'EPERM'; }
  }

  // The pid of the copy already running, or null once this copy holds the lock.
  acquire() {
    let other = NaN;
    try { other = Number(this.fs.readFileSync(this.file, 'utf8')); } catch { /* no lock yet */ }
    if (other && other !== this.pid && this.alive(other)) return other;
    this.fs.writeFileSync(this.file, String(this.pid));
    this.held = true;
    return null;
  }

  release() {
    if (!this.held) return;
    try {
      if (Number(this.fs.readFileSync(this.file, 'utf8')) === this.pid) this.fs.unlinkSync(this.file);
    } catch { /* already gone */ }
    this.held = false;
  }
}

module.exports = { InstanceLock };
