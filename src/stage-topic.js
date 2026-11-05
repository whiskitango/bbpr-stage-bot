// What the Stage says it is about: the station's name, and the song on air
// when there is one. Discord caps a Stage topic at 120 characters.

const MAX = 120;

class StageTopic {
  static format(base, song = '') {
    const text = song ? `${base} - ${song}` : base;
    return text.length <= MAX ? text : `${text.slice(0, MAX - 1)}…`;
  }
}

module.exports = { StageTopic };
