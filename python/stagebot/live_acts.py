"""The station's live acts, spelled the way they should appear in Discord.
AzuraCast's streamer name may be written differently ("whiski", "dj_whiski",
"DJ WHISKI"), so names are matched ignoring case, spaces, punctuation and a
leading title such as "DJ" or "Judge". A name not on the list is shown as
AzuraCast sends it."""

from __future__ import annotations

import re
from typing import Iterable

ACTS = (
    'DJ Whiski',
    'DJ Tekeela',
    'DJ Mossa',
    'DJ Sheal',
    'DJ Kando',
    'DJ Sabellwind',
    'Judge Holdenn',
)


class LiveActs:
    def __init__(self, names: Iterable[str] = ACTS):
        self.by_key = {self.key_of(name): name for name in names}

    @staticmethod
    def key_of(name: str) -> str:
        plain = re.sub(r'[^a-z0-9]', '', (name or '').lower())
        bare = re.sub(r'^(dj|judge)', '', plain)
        return bare or plain

    def name_of(self, raw: str) -> str:
        """The list's spelling of this name, or the name itself if unknown."""
        return self.by_key.get(self.key_of(raw)) or (raw or '').strip()

    def same(self, a: str, b: str) -> bool:
        return self.key_of(a) == self.key_of(b)
