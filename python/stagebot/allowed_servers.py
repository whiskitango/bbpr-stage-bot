"""Which Discord servers the bot will play in. With ALLOWED_GUILD_IDS set it
refuses every other server; empty means any server it has been invited to
(fine once "Public Bot" is off in the developer portal)."""

from __future__ import annotations

from typing import Iterable


class AllowedServers:
    def __init__(self, ids: Iterable[str] = ()):
        self.ids = {str(i) for i in ids if i}

    @property
    def open(self) -> bool:
        return not self.ids

    def allows(self, guild_id) -> bool:
        return self.open or str(guild_id) in self.ids
