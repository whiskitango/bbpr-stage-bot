import unittest
from types import SimpleNamespace

import discord
from aiohttp.test_utils import TestClient, TestServer

from stagebot.config import Config
from stagebot.stage_audience import StageAudience
from stagebot.status_report import StatusReport
from stagebot.status_server import StatusServer

BOT = 1
TOKEN = 'x' * 32


def state(deaf=False, self_deaf=False):
    return SimpleNamespace(deaf=deaf, self_deaf=self_deaf)


class FakeGuild:
    def __init__(self, name, bots=()):
        self.name = name
        self.bots = set(bots)

    def get_member(self, user_id):
        if user_id in self.bots:
            return SimpleNamespace(bot=True)
        return SimpleNamespace(bot=False) if user_id % 2 else None   # some members unknown


def channel(name, guild, states):
    return SimpleNamespace(name=name, guild=guild, voice_states=states)


def presence(channel_id, ready=True, connected=True):
    voice = SimpleNamespace(is_connected=lambda: connected)
    return SimpleNamespace(channel_id=channel_id, channel=None, ready=ready, voice=voice)


class StageAudienceTest(unittest.TestCase):
    def test_counts_people_but_not_bots_or_the_deafened(self):
        guild = FakeGuild('Pirates', bots={7})
        room = channel('Radio Room', guild, {
            BOT: state(), 7: state(),            # this bot, and another bot
            3: state(), 4: state(), 5: state(),  # people (4 is not in the member cache)
            9: state(self_deaf=True), 11: state(deaf=True),
        })
        self.assertEqual(StageAudience.count(room, BOT), 3)
        self.assertEqual(StageAudience.count(None, BOT), 0)
        self.assertEqual(StageAudience.count(channel('Empty', guild, {}), BOT), 0)


class StatusReportTest(unittest.TestCase):
    def test_totals_only_channels_that_are_playing(self):
        a = channel('Radio Room', FakeGuild('Pirates'), {BOT: state(), 3: state(), 5: state()})
        b = channel('Lounge', FakeGuild('Friends'), {BOT: state(), 3: state()})
        channels = {10: a, 20: b}
        client = SimpleNamespace(user=SimpleNamespace(id=BOT), get_channel=channels.get,
                                 guilds=[a.guild, b.guild, FakeGuild('Installed, not playing')])
        fleet = SimpleNamespace(presences=lambda: [presence(10), presence(20, ready=False)])
        report = StatusReport(client, fleet, 'booty_bay_pirate_radio', clock=lambda: 1_790_000_000.5).build()
        self.assertEqual(report, {
            'station': 'booty_bay_pirate_radio',
            'at': 1_790_000_000_500,
            'listeners': 2,
            'servers': 3,
            'channels': [
                {'server': 'Pirates', 'channel': 'Radio Room', 'kind': 'voice', 'playing': True, 'listeners': 2},
                {'server': 'Friends', 'channel': 'Lounge', 'kind': 'voice', 'playing': False, 'listeners': 1},
            ],
        })

    def test_a_stage_says_so(self):
        stage = discord.StageChannel.__new__(discord.StageChannel)
        client = SimpleNamespace(user=None, get_channel=lambda _id: stage)
        entry = StatusReport(client, None, 's').channel(presence(10))
        self.assertEqual(entry['kind'], 'stage')


class StatusConfigTest(unittest.TestCase):
    def test_station_comes_from_the_stream_unless_named(self):
        self.assertEqual(Config.from_env({}).station, 'booty_bay_pirate_radio')
        self.assertEqual(Config.from_env({'STATION': 'other'}).station, 'other')
        self.assertEqual(Config.from_env({'STREAM_URL': 'https://x/radio.mp3'}).station, '')

    def test_status_page_needs_a_long_token(self):
        base = {'DISCORD_TOKEN': 't'}
        self.assertEqual(Config.from_env(base).missing(), [], 'off by default')
        self.assertEqual(Config.from_env({**base, 'STATUS_PORT': '8790', 'STATUS_TOKEN': 'short'}).missing(),
                         ['STATUS_TOKEN (at least 24 characters)'])
        ready = Config.from_env({**base, 'STATUS_PORT': '8790', 'STATUS_TOKEN': TOKEN})
        self.assertEqual(ready.missing(), [])
        self.assertEqual((ready.status_port, ready.status_host), (8790, '127.0.0.1'))
        half = Config.from_env({**base, 'STATUS_PORT': '8790', 'STATUS_TOKEN': TOKEN, 'STATUS_TLS_CERT': 'c'})
        self.assertEqual(half.missing(), ['STATUS_TLS_CERT and STATUS_TLS_KEY (both, or neither)'])
        self.assertEqual(Config.from_env({**base, 'STATUS_PORT': 'x'}).status_port, 0)


class StageBotWiringTest(unittest.IsolatedAsyncioTestCase):
    async def test_the_bot_builds_with_and_without_the_status_page(self):
        # discord.Client has a `status` property of its own; the page must not
        # be stored under a name the client already uses.
        import tempfile
        from stagebot.stage_bot import StageBot
        with tempfile.TemporaryDirectory() as d:
            on = Config.from_env({'DISCORD_TOKEN': 't', 'STATUS_PORT': '8790', 'STATUS_TOKEN': TOKEN, 'DATA_DIR': d})
            bot = StageBot(on, ffmpeg='ffmpeg')
            self.assertIsInstance(bot.status_page, StatusServer)
            self.assertEqual(bot.status_page.report()['station'], 'booty_bay_pirate_radio')
            await bot.close()
            off = StageBot(Config.from_env({'DISCORD_TOKEN': 't', 'DATA_DIR': d}), ffmpeg='ffmpeg')
            self.assertIsNone(off.status_page)
            await off.close()


class StatusServerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.server = StatusServer('127.0.0.1', 0, TOKEN, lambda: {'listeners': 4})
        self.client = TestClient(TestServer(self.server.app()))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_answers_with_the_token(self):
        response = await self.client.get('/status', headers={'Authorization': f'Bearer {TOKEN}'})
        self.assertEqual(response.status, 200)
        self.assertEqual(await response.json(), {'listeners': 4})
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    async def test_refuses_without_it(self):
        for headers in ({}, {'Authorization': 'Bearer wrong'}, {'Authorization': TOKEN},
                        {'Authorization': f'Basic {TOKEN}'}):
            response = await self.client.get('/status', headers=headers)
            self.assertEqual(response.status, 401, headers)
            self.assertNotIn('listeners', await response.text())

    async def test_serves_nothing_else(self):
        auth = {'Authorization': f'Bearer {TOKEN}'}
        self.assertEqual((await self.client.get('/', headers=auth)).status, 404)
        self.assertEqual((await self.client.post('/status', headers=auth)).status, 405)

    def test_no_token_lets_nobody_in(self):
        self.assertFalse(StatusServer('127.0.0.1', 0, '', dict).authorized('Bearer '))


if __name__ == '__main__':
    unittest.main()
