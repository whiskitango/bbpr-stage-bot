import asyncio
import unittest
from types import SimpleNamespace

import discord

from stagebot import stage_presence
from stagebot.stage_presence import ChannelGone, StagePresence


class FakeMember:
    def __init__(self, channel_id, refuse=True):
        self.voice = SimpleNamespace(channel=SimpleNamespace(id=channel_id), suppress=True)
        self.refuse = refuse
        self.edits = 0
        self.requests = 0

    async def edit(self, suppress):
        self.edits += 1
        if self.refuse:
            raise discord.Forbidden(SimpleNamespace(status=403, reason='Forbidden'), 'Missing Access')
        self.voice.suppress = suppress

    async def request_to_speak(self):
        self.requests += 1


class PresenceTest(unittest.TestCase):
    def presence(self, member):
        p = StagePresence(client=None, channel_id=5, stream=None, topic='T')
        p.channel = SimpleNamespace(guild=SimpleNamespace(me=member, name='G'), name='Stage')
        return p

    def test_a_refused_speaker_asks_once_then_waits(self):
        member = FakeMember(5)
        p = self.presence(member)

        async def run():
            for _ in range(5):
                await p.speak()
        asyncio.run(run())
        self.assertEqual((member.edits, member.requests), (1, 1))

        p.refused_at -= stage_presence.SPEAK_RETRY_S + 1   # time passes, permission granted
        member.refuse = False
        asyncio.run(p.speak())
        self.assertEqual(member.edits, 2)
        self.assertFalse(member.voice.suppress)

    def test_a_refusal_is_logged_once_not_at_every_retry(self):
        member = FakeMember(5)
        p = self.presence(member)
        with self.assertLogs('stagebot', level='WARNING') as logs:
            for _ in range(3):
                asyncio.run(p.speak())
                p.refused_at -= stage_presence.SPEAK_RETRY_S + 1
        self.assertEqual(member.edits, 3, 'it still tries again each time')
        self.assertEqual(len(logs.output), 1)
        self.assertIn('nobody there hears it', logs.output[0])
        member.refuse = False
        asyncio.run(p.speak())
        self.assertFalse(p.refusal_logged, 'a later refusal is said again')

    def test_a_deleted_channel_is_given_up_and_forgotten(self):
        gone = []
        p = StagePresence(client=None, channel_id=5, stream=None, topic='T', on_gone=gone.append)

        async def join():
            raise ChannelGone('channel 5: Unknown Channel')
        p.connect_and_play = join
        p.voice = None
        stage_presence.CHECK_S, saved = 0, stage_presence.CHECK_S
        try:
            p.watchdog = object()
            asyncio.run(p.keep_alive())
        finally:
            stage_presence.CHECK_S = saved
        self.assertEqual(gone, [p])
        self.assertTrue(p.leaving)


if __name__ == '__main__':
    unittest.main()
