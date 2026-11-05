"""How many people are listening in one Stage or voice channel. Everyone in
the channel counts, speakers and audience alike, except bots (this one
included) and anyone who has deafened themselves, since they can't hear it.

Discord sends voice states with the voice_states intent, so this needs no
member list. A member the bot hasn't seen yet counts as a person: only a
member known to be a bot is left out."""

from __future__ import annotations

from typing import Optional


class StageAudience:
    @staticmethod
    def count(channel, bot_id: Optional[int]) -> int:
        if channel is None:
            return 0
        states = getattr(channel, 'voice_states', None) or {}
        guild = getattr(channel, 'guild', None)
        listeners = 0
        for user_id, state in states.items():
            if user_id == bot_id:
                continue
            if getattr(state, 'deaf', False) or getattr(state, 'self_deaf', False):
                continue
            member = guild.get_member(user_id) if guild else None
            if member is not None and member.bot:
                continue
            listeners += 1
        return listeners
