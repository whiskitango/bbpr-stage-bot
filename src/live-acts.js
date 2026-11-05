// The station's live acts, spelled the way they should appear in Discord.
// AzuraCast's streamer name may be written differently ("whiski",
// "dj_whiski", "DJ WHISKI"), so names are matched ignoring case, spaces,
// punctuation and a leading title such as "DJ" or "Judge". A name not on the
// list is shown as AzuraCast sends it.

const ACTS = [
  'DJ Whiski',
  'DJ Tekeela',
  'DJ Mossa',
  'DJ Sheal',
  'DJ Kando',
  'DJ Sabellwind',
  'Judge Holdenn',
];

class LiveActs {
  constructor(names = ACTS) {
    this.byKey = new Map(names.map((name) => [LiveActs.keyOf(name), name]));
  }

  static keyOf(name) {
    const plain = String(name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    const bare = plain.replace(/^(dj|judge)/, '');
    return bare || plain;
  }

  // The list's spelling of this name, or the name itself (trimmed) if unknown.
  nameOf(raw) {
    return this.byKey.get(LiveActs.keyOf(raw)) || String(raw || '').trim();
  }

  // True when two spellings name the same act.
  same(a, b) {
    return LiveActs.keyOf(a) === LiveActs.keyOf(b);
  }
}

module.exports = { LiveActs, ACTS };
