"""How loud the bot plays, as a percentage of the station's own level.

The station's stream is mastered loud, and Discord plays a bot at full
volume until each listener turns it down themselves, so joining a Stage at
100% blasts everyone in it. The bot plays quieter by default, and ffmpeg
lowers the level once for every server (see radio_stream.py)."""

from __future__ import annotations


class Volume:
    DEFAULT = 50
    LOWEST = 1
    HIGHEST = 100      # above the station's level would clip

    def __init__(self, percent: int = DEFAULT):
        self.percent = max(self.LOWEST, min(self.HIGHEST, int(percent)))

    @classmethod
    def parse(cls, text: str) -> 'Volume':
        """Reads "50" or "50%"; anything else, or nothing, gives the default."""
        try:
            return cls(int((text or '').strip().rstrip('%')))
        except ValueError:
            return cls()

    @property
    def gain(self) -> float:
        return self.percent / 100

    def ffmpeg_filter(self) -> str:
        return f'volume={self.gain:.2f}'

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Volume) and other.percent == self.percent

    def __repr__(self) -> str:
        return f'Volume({self.percent}%)'
