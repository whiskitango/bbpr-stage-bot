const test = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { Config } = require('../src/config');
const { Backoff } = require('../src/backoff');
const { StageTopic } = require('../src/stage-topic');
const { NowPlayingWatch } = require('../src/now-playing-watch');
const { FfmpegLocator } = require('../src/ffmpeg-locator');
const { StreamSource } = require('../src/stream-source');
const { RadioPlayer } = require('../src/radio-player');

const quiet = { info() {}, warn() {}, error() {} };

test('Config names the missing settings and defaults the stream', () => {
  const c = Config.fromEnv({});
  assert.deepEqual(c.missing(), ['DISCORD_TOKEN']);
  assert.deepEqual(c.stageChannelIds, []);
  assert.match(c.streamUrl, /radio\.mp3$/);
  const ready = Config.fromEnv({ DISCORD_TOKEN: ' t ', STAGE_CHANNEL_ID: '123, 456', ALLOWED_GUILD_IDS: '9', BITRATE: '96', NOW_PLAYING_URL: '', DATA_DIR: '/d' });
  assert.deepEqual(ready.stageChannelIds, ['123', '456']);
  assert.deepEqual(ready.allowedGuildIds, ['9']);
  assert.match(ready.channelsFile, /channels.json$/);
  assert.deepEqual(ready.missing(), []);
  assert.equal(ready.token, 't');
  assert.equal(ready.bitrate, 96);
  assert.equal(ready.nowPlayingUrl, '');
});

test('Backoff doubles to a cap and starts short again after a healthy run', () => {
  let t = 0;
  const b = new Backoff({ first: 1000, max: 4000, healthyAfter: 10000, now: () => t });
  assert.deepEqual([b.next(), b.next(), b.next(), b.next()], [1000, 2000, 4000, 4000]);
  b.started(); t += 3000;
  assert.equal(b.next(), 4000);          // a short run is still failing
  b.started(); t += 20000;
  assert.equal(b.next(), 1000);          // a long run was healthy
});

test('StageTopic adds the song and keeps within 120 characters', () => {
  assert.equal(StageTopic.format('BBPR'), 'BBPR');
  assert.equal(StageTopic.format('BBPR', 'A - B'), 'BBPR - A - B');
  const long = StageTopic.format('BBPR', 'x'.repeat(300));
  assert.equal(long.length, 120);
  assert.ok(long.endsWith('…'));
});

test('NowPlayingWatch reads the song, marks live DJs and reports changes only', async () => {
  assert.equal(NowPlayingWatch.songOf({ now_playing: { song: { artist: 'A', title: 'B' } } }), 'A - B');
  assert.equal(NowPlayingWatch.songOf({ now_playing: { song: { text: 'Just text' } } }), 'Just text');
  const live = { is_live: true, streamer_name: 'DJ Whiski' };
  assert.equal(NowPlayingWatch.songOf({ now_playing: { song: { artist: 'A', title: 'Song Name' } }, live }), 'DJ Whiski - Song Name');
  assert.equal(NowPlayingWatch.songOf({ now_playing: { song: { text: 'Mix 3' } }, live }), 'DJ Whiski - Mix 3');
  assert.equal(NowPlayingWatch.songOf({ now_playing: { song: { title: '' } }, live }), 'DJ Whiski');
  assert.equal(NowPlayingWatch.songOf({ now_playing: { song: { title: 'DJ Whiski' } }, live }), 'DJ Whiski');
  const as = (name, title = 'T') => NowPlayingWatch.songOf({ now_playing: { song: { title } }, live: { is_live: true, streamer_name: name } });
  assert.equal(as('whiski'), 'DJ Whiski - T');
  assert.equal(as('dj_tekeela'), 'DJ Tekeela - T');
  assert.equal(as('MOSSA'), 'DJ Mossa - T');
  assert.equal(as('holdenn'), 'Judge Holdenn - T');
  assert.equal(as('Judge Holdenn', 'holdenn'), 'Judge Holdenn');
  assert.equal(as('Guest Act'), 'Guest Act - T');
  assert.equal(NowPlayingWatch.songOf({}), '');

  const bodies = [
    { now_playing: { song: { artist: 'A', title: 'B' } } },
    { now_playing: { song: { artist: 'A', title: 'B' } } },
    { now_playing: { song: { artist: 'C', title: 'D' } } },
  ];
  const seen = [];
  const w = new NowPlayingWatch({
    url: 'x', log: quiet, onChange: (s) => seen.push(s),
    fetcher: async () => ({ ok: true, json: async () => bodies.shift() }),
  });
  await w.check(); await w.check(); await w.check();
  assert.deepEqual(seen, ['A - B', 'C - D']);

  const failing = new NowPlayingWatch({ url: 'x', log: quiet, onChange: () => assert.fail(), fetcher: async () => { throw new Error('down'); } });
  await failing.check();                 // no throw
});

test('FfmpegLocator prefers FFMPEG_PATH, then the bundled copy, then the PATH', () => {
  assert.equal(FfmpegLocator.find({ env: { FFMPEG_PATH: '/x/ffmpeg' }, bundled: '/b' }), '/x/ffmpeg');
  assert.equal(FfmpegLocator.find({ env: {}, bundled: '/b', exists: () => true }), '/b');
  assert.equal(FfmpegLocator.find({ env: {}, bundled: '/b', exists: () => false }), 'ffmpeg');
  assert.equal(FfmpegLocator.find({ env: {}, bundled: null }), 'ffmpeg');
});

test('StreamSource asks ffmpeg for reconnecting Ogg Opus at the set bitrate', () => {
  const args = StreamSource.args('http://s/radio.mp3', 96);
  assert.equal(args[args.indexOf('-i') + 1], 'http://s/radio.mp3');
  assert.equal(args[args.indexOf('-c:a') + 1], 'libopus');
  assert.equal(args[args.indexOf('-b:a') + 1], '96k');
  assert.equal(args[args.indexOf('-f') + 1], 'ogg');
  assert.ok(args.includes('-reconnect_streamed'));
});

test('RadioPlayer reopens the stream after it ends, once per end, and not after stop', () => {
  const player = new EventEmitter();
  player.played = 0;
  player.play = () => { player.played += 1; };
  player.stop = () => {};
  const source = { opened: 0, closed: 0, open() { this.opened += 1; return {}; }, close() { this.closed += 1; } };
  const pending = [];
  const timers = { setTimeout: (fn) => { pending.push(fn); return pending.length; }, clearTimeout: () => { pending.length = 0; } };
  const radio = new RadioPlayer({ source, player, timers, log: quiet, backoff: new Backoff({ now: () => 0 }) });

  radio.start();
  assert.equal(source.opened, 1);
  player.emit('idle'); player.emit('idle');   // two idles, one retry
  assert.equal(pending.length, 1);
  pending.shift()();
  assert.equal(source.opened, 2);

  player.emit('idle');
  radio.stop();
  assert.equal(pending.length, 0);
  assert.equal(source.closed, 1);
});

test('InstanceLock refuses a second copy, takes over a dead one, and releases its own', () => {
  const { InstanceLock } = require('../src/instance-lock');
  const files = {};
  const fsys = {
    readFileSync: (f) => { if (!(f in files)) throw new Error('ENOENT'); return files[f]; },
    writeFileSync: (f, v) => { files[f] = v; },
    unlinkSync: (f) => { delete files[f]; },
  };
  const live = new Set([100]);
  const a = new InstanceLock({ file: 'lock', pid: 100, fsys, alive: (p) => live.has(p) });
  assert.equal(a.acquire(), null);
  const b = new InstanceLock({ file: 'lock', pid: 200, fsys, alive: (p) => live.has(p) });
  assert.equal(b.acquire(), 100);        // a is still running
  live.delete(100);
  assert.equal(b.acquire(), null);       // a died without cleaning up
  a.release();                           // a's release must not remove b's lock
  assert.equal(files.lock, '200');
  b.release();
  assert.equal(files.lock, undefined);
});
