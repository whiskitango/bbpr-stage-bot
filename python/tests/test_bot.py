import tempfile
import unittest
from pathlib import Path

from stagebot.allowed_servers import AllowedServers
from stagebot.backoff import Backoff
from stagebot.channel_store import ChannelStore
from stagebot.config import Config
from stagebot.env_file import EnvFile
from stagebot.instance_lock import InstanceLock
from stagebot.live_acts import LiveActs
from stagebot.now_playing import NowPlayingWatch
from stagebot.radio_stream import SILENCE, FfmpegCommand, RadioStream
from stagebot.volume import Volume


class ConfigTest(unittest.TestCase):
    def test_names_missing_settings_and_defaults_the_stream(self):
        c = Config.from_env({})
        self.assertEqual(c.missing(), ['DISCORD_TOKEN'])
        self.assertTrue(c.stream_url.endswith('radio.mp3'))
        ready = Config.from_env({'DISCORD_TOKEN': ' t ', 'STAGE_CHANNEL_ID': '123, 456', 'ALLOWED_GUILD_IDS': '9',
                                 'BITRATE': '96', 'NOW_PLAYING_URL': '', 'VOICE_DEBUG': 'yes'})
        self.assertEqual(ready.token, 't')
        self.assertEqual(ready.stage_channel_ids, ['123', '456'])
        self.assertEqual(ready.allowed_guild_ids, ['9'])
        self.assertEqual(ready.bitrate, 96)
        self.assertEqual(ready.now_playing_url, '')
        self.assertTrue(ready.voice_debug)
        self.assertEqual(ready.missing(), [])

    def test_volume_defaults_to_half_and_reads_a_percentage(self):
        self.assertEqual(Config.from_env({}).volume, Volume(50))
        self.assertEqual(Config.from_env({'VOLUME': '30%'}).volume, Volume(30))
        self.assertEqual(Config.from_env({'VOLUME': 'loud'}).volume, Volume(50))


class EnvFileTest(unittest.TestCase):
    def test_parses_and_never_overrides(self):
        self.assertEqual(EnvFile.parse('# c\nA=1\nB = "two"\n\nC\n'), {'A': '1', 'B': 'two'})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '.env'
            p.write_text('A=file\nB=file\n')
            env = {'A': 'set'}
            self.assertTrue(EnvFile(p).load(env))
            self.assertEqual(env, {'A': 'set', 'B': 'file'})


class SongTest(unittest.TestCase):
    def test_reads_song_and_names_live_acts(self):
        song_of = NowPlayingWatch.song_of
        self.assertEqual(song_of({'now_playing': {'song': {'artist': 'A', 'title': 'B'}}}), 'A - B')
        self.assertEqual(song_of({'now_playing': {'song': {'text': 'Just text'}}}), 'Just text')
        self.assertEqual(song_of({}), '')

        def live(name, title='T'):
            return song_of({'now_playing': {'song': {'title': title}}, 'live': {'is_live': True, 'streamer_name': name}})

        self.assertEqual(live('whiski'), 'DJ Whiski - T')
        self.assertEqual(live('dj_tekeela'), 'DJ Tekeela - T')
        self.assertEqual(live('MOSSA'), 'DJ Mossa - T')
        self.assertEqual(live('holdenn'), 'Judge Holdenn - T')
        self.assertEqual(live('Judge Holdenn', 'holdenn'), 'Judge Holdenn')
        self.assertEqual(live('DJ Whiski', ''), 'DJ Whiski')
        self.assertEqual(live('Guest Act'), 'Guest Act - T')

    def test_live_acts_match_loosely(self):
        acts = LiveActs()
        self.assertEqual(acts.name_of('  sabellwind '), 'DJ Sabellwind')
        self.assertTrue(acts.same('DJ Kando', 'kando'))



class ChannelStoreTest(unittest.TestCase):
    def test_one_channel_per_server_survives_reload(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'sub' / 'channels.json'
            s = ChannelStore(f).load()
            s.set('1', '10')
            s.set('1', '11')
            s.set('2', '20')
            s.remove('2')
            self.assertEqual(ChannelStore(f).load().all(), [('1', '11')])


class AllowedServersTest(unittest.TestCase):
    def test_open_when_empty_and_strict_otherwise(self):
        self.assertTrue(AllowedServers().allows(5))
        only = AllowedServers(['9'])
        self.assertTrue(only.allows(9))
        self.assertFalse(only.allows('8'))


class BackoffTest(unittest.TestCase):
    def test_doubles_to_max_and_resets_after_healthy_play(self):
        t = [0.0]
        b = Backoff(first=2, maximum=8, healthy_after=60, now=lambda: t[0])
        self.assertEqual([b.next(), b.next(), b.next(), b.next()], [2, 4, 8, 8])
        b.started()
        t[0] = 61
        self.assertEqual(b.next(), 2)


class InstanceLockTest(unittest.TestCase):
    def test_refuses_a_live_copy_and_takes_over_a_dead_one(self):
        class Alive:
            @staticmethod
            def alive(pid):
                return pid == 111

        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / 'lock'
            f.write_text('111')
            self.assertEqual(InstanceLock(f, pid=222, check=Alive).acquire(), 111)
            f.write_text('333')
            mine = InstanceLock(f, pid=222, check=Alive)
            self.assertIsNone(mine.acquire())
            mine.release()
            self.assertFalse(f.exists())


class RadioStreamTest(unittest.TestCase):
    def test_every_listener_gets_each_packet_and_silence_when_empty(self):
        stream = RadioStream('http://x')
        a, b = stream.listen(), stream.listen()
        stream.broadcast(b'p1')
        self.assertEqual((a.read(), b.read()), (b'p1', b'p1'))
        self.assertEqual(a.read(), SILENCE)
        a.cleanup()
        stream.broadcast(b'p2')
        self.assertEqual(b.read(), b'p2')
        self.assertEqual(len(stream.listeners), 1)

    def test_listener_drops_old_packets_to_stay_live(self):
        stream = RadioStream('http://x')
        a = stream.listen()
        for i in range(200):
            stream.broadcast(bytes([i]))
        self.assertEqual(a.read(), bytes([50]))

    def test_ffmpeg_makes_ogg_opus_at_the_bitrate(self):
        args = FfmpegCommand.args('ff', 'http://s', 96)
        self.assertEqual(args[0], 'ff')
        self.assertIn('96k', args)
        self.assertEqual(args[-1], 'pipe:1')
        self.assertIn('ogg', args)

    def test_ffmpeg_plays_at_half_volume_unless_told_otherwise(self):
        args = FfmpegCommand.args('ff', 'http://s', 96)
        self.assertEqual(args[args.index('-af') + 1], 'volume=0.50')
        args = FfmpegCommand.args('ff', 'http://s', 96, Volume(25))
        self.assertEqual(args[args.index('-af') + 1], 'volume=0.25')
        # The filter must come after the input, or ffmpeg ignores it.
        self.assertGreater(args.index('-af'), args.index('-i'))


class VolumeTest(unittest.TestCase):
    def test_keeps_within_1_and_100_percent(self):
        self.assertEqual(Volume(0).percent, 1)
        self.assertEqual(Volume(250).percent, 100)
        self.assertEqual(Volume.parse(' 75 ').percent, 75)
        self.assertEqual(Volume.parse('').percent, 50)
        self.assertEqual(Volume(50).ffmpeg_filter(), 'volume=0.50')


if __name__ == '__main__':
    unittest.main()
