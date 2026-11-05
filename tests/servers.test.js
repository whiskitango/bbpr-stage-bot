const test = require('node:test');
const assert = require('node:assert/strict');
const { PermissionFlagsBits, InteractionContextType } = require('discord.js');
const { AllowedServers } = require('../src/allowed-servers');
const { ChannelStore } = require('../src/channel-store');
const { StageFleet } = require('../src/stage-fleet');
const { RadioCommands } = require('../src/radio-commands');

const quiet = { info() {}, warn() {}, error() {} };

class MemoryFs {
  constructor() { this.files = {}; }
  readFileSync(f) { if (!(f in this.files)) { const e = new Error('nope'); e.code = 'ENOENT'; throw e; } return this.files[f]; }
  writeFileSync(f, v) { this.files[f] = v; }
  renameSync(a, b) { this.files[b] = this.files[a]; delete this.files[a]; }
  mkdirSync() {}
}

class FakePresence {
  constructor(opts) { Object.assign(this, opts); this.left = false; this.topics = []; this.fail = FakePresence.nextFail; FakePresence.nextFail = null; }
  async join() { if (this.fail) throw this.fail; this.channel = { id: this.channelId }; }
  start() { this.started = true; }
  leave() { this.left = true; }
  async setTopic(t) { this.topics.push(t); }
  onOwnVoiceState() {}
}

test('AllowedServers: empty allows any server, a list allows only those', () => {
  assert.ok(AllowedServers.parse('').allows('1'));
  const only = AllowedServers.parse('1, 2');
  assert.ok(only.allows('2'));
  assert.ok(!only.allows('3'));
  assert.ok(!only.open);
});

test('ChannelStore keeps one channel per server and survives a reload', () => {
  const fsys = new MemoryFs();
  const a = new ChannelStore({ file: 'c.json', fsys, log: quiet }).load();
  a.set('g1', 'c1'); a.set('g2', 'c2'); a.set('g1', 'c3');
  a.remove('g2');
  const b = new ChannelStore({ file: 'c.json', fsys, log: quiet }).load();
  assert.deepEqual(b.all(), [{ guildId: 'g1', channelId: 'c3' }]);
});

test('StageFleet joins, replaces, forgets gone channels and saves as it goes', async () => {
  const store = new ChannelStore({ file: 'c.json', fsys: new MemoryFs(), log: quiet });
  const made = [];
  const fleet = new StageFleet({ store, log: quiet, makePresence: (o) => { const p = new FakePresence(o); made.push(p); return p; } });

  await fleet.join('g1', 'c1');
  await fleet.join('g1', 'c2');                       // same server: replaces
  assert.equal(made[0].left, true);
  assert.equal(store.get('g1'), 'c2');

  FakePresence.nextFail = new Error('no access');
  await assert.rejects(fleet.join('g2', 'c9'));        // a failed join keeps nothing
  assert.equal(store.get('g2'), null);
  assert.equal(fleet.size, 1);

  await fleet.setTopic('Song');
  assert.deepEqual(made[1].topics, ['Song']);
  await fleet.join('g3', 'c3');
  assert.equal(fleet.get('g3').wantedTopic, 'Song');   // a later join gets the current song

  fleet.get('g3').onGone();                            // channel deleted
  assert.equal(fleet.get('g3'), null);
  assert.equal(store.get('g3'), null);

  assert.equal(fleet.leave('g1'), true);
  assert.equal(fleet.leave('g1'), false);
  assert.deepEqual(store.all(), []);
});

test('StageFleet.startAll rejoins every saved channel and leaveAll keeps them saved', () => {
  const store = new ChannelStore({ file: 'c.json', fsys: new MemoryFs(), log: quiet });
  store.set('g1', 'c1'); store.set('g2', 'c2');
  const fleet = new StageFleet({ store, log: quiet, makePresence: (o) => new FakePresence(o) });
  fleet.startAll();
  assert.ok(fleet.get('g1').started && fleet.get('g2').started);
  fleet.leaveAll();
  assert.equal(store.all().length, 2);
});

test('/radio is hidden from members without Manage Channels and works only in servers', () => {
  const json = RadioCommands.definition('BBPR').toJSON();
  assert.equal(json.name, 'radio');
  assert.equal(json.default_member_permissions, String(PermissionFlagsBits.ManageChannels));
  assert.deepEqual(json.contexts, [InteractionContextType.Guild]);
  assert.deepEqual(json.options.map((o) => o.name), ['join', 'leave', 'status']);
});

test('RadioCommands.missing names what the bot lacks', () => {
  const perms = { has: (p) => p === PermissionFlagsBits.ViewChannel };
  assert.deepEqual(RadioCommands.missing(perms, [PermissionFlagsBits.ViewChannel, PermissionFlagsBits.Speak]), ['Speak']);
  assert.deepEqual(RadioCommands.missing(null, [PermissionFlagsBits.Connect]), ['Connect']);
});

function fakeInteraction({ guildId = 'g1', sub = 'leave' } = {}) {
  const i = {
    commandName: 'radio', guildId, guild: { name: 'Test' }, user: { tag: 'someone' },
    deferred: false, replied: false, replies: [],
    isChatInputCommand: () => true, inGuild: () => true,
    options: { getSubcommand: () => sub, getChannel: () => null },
    member: { voice: { channel: null } },
    reply: async ({ content }) => { i.replied = true; i.replies.push(content); },
    editReply: async ({ content }) => { i.replies.push(content); },
  };
  return i;
}

test('RadioCommands refuses servers not on the allowed list', async () => {
  let left = false;
  const cmds = new RadioCommands({ fleet: { leave: () => { left = true; return true; } }, allowed: AllowedServers.parse('g1'), log: quiet });
  const outsider = fakeInteraction({ guildId: 'g2' });
  await cmds.handle(outsider);
  assert.equal(left, false);
  assert.match(outsider.replies[0], /isn't set up/);

  const member = fakeInteraction({ guildId: 'g1' });
  await cmds.handle(member);
  assert.equal(left, true);
  assert.match(member.replies[0], /Stopped/);
});

test('/radio join with no channel asks for one', async () => {
  const cmds = new RadioCommands({ fleet: {}, allowed: AllowedServers.parse(''), log: quiet });
  const i = fakeInteraction({ sub: 'join' });
  await cmds.handle(i);
  assert.match(i.replies[0], /Join a Stage first/);
});
