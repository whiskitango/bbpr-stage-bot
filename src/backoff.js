// How long to wait before reopening the stream: 2 s, then doubling to a
// minute while it keeps failing. A stream that played for a while before
// ending counts as healthy, so the next wait starts short again.

class Backoff {
  constructor({ first = 2000, max = 60000, healthyAfter = 60000, now = () => Date.now() } = {}) {
    this.first = first;
    this.max = max;
    this.healthyAfter = healthyAfter;
    this.now = now;
    this.delay = first;
    this.startedAt = null;
  }

  started() { this.startedAt = this.now(); }

  next() {
    if (this.startedAt !== null && this.now() - this.startedAt >= this.healthyAfter) this.delay = this.first;
    const wait = this.delay;
    this.delay = Math.min(this.delay * 2, this.max);
    this.startedAt = null;
    return wait;
  }
}

module.exports = { Backoff };
