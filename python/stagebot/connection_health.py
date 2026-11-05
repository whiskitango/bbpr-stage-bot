"""Decides when a voice connection has really dropped. discord.py reconnects
by itself, and Discord moves a Stage speaker to another voice server now and
then (always right after it becomes a speaker); for those few seconds the
connection reads as "not connected". Rejoining then would cut that reconnect
short and set off another move, so the bot only rejoins after several checks
in a row find it disconnected, or once discord.py has given up on it."""

from __future__ import annotations


class ConnectionHealth:
    def __init__(self, patience: int = 3):
        self.patience = patience
        self.misses = 0

    def needs_rejoin(self, connected: bool, given_up: bool = False) -> bool:
        if connected:
            self.misses = 0
            return False
        if given_up:
            self.misses = 0
            return True
        self.misses += 1
        if self.misses >= self.patience:
            self.misses = 0
            return True
        return False
