import logging
import tempfile
import unittest
from pathlib import Path

from stagebot.log_file import LogFile
from stagebot.radio_stream import FfmpegCommand, RadioStream
from stagebot.stream_stall import StreamStall


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakeProc:
    def __init__(self):
        self.killed = False

    def poll(self):
        return 0 if self.killed else None

    def kill(self):
        self.killed = True


class StreamStallTest(unittest.TestCase):
    def test_quiet_past_the_limit_is_a_stall_and_a_packet_clears_it(self):
        clock = Clock()
        stall = StreamStall(limit=20, now=clock)
        clock.t += 19
        self.assertFalse(stall.stalled())
        clock.t += 1
        self.assertTrue(stall.stalled())
        stall.fed()
        self.assertFalse(stall.stalled())
        clock.t += 30
        stall.reset()
        self.assertFalse(stall.stalled(), 'a reopened stream gets the whole limit again')


class StallWatchTest(unittest.TestCase):
    def stream(self, clock):
        stream = RadioStream('http://x', stall=StreamStall(limit=20, now=clock))
        stream.check_s = 0.001
        return stream

    def test_a_stalled_stream_is_ended_so_it_reopens_and_the_log_says_why(self):
        clock = Clock()
        stream = self.stream(clock)
        clock.t += 25
        proc = FakeProc()
        with self.assertLogs('stagebot', level='WARNING') as logs:
            self.assertTrue(stream.watch_stall(proc))
        self.assertTrue(proc.killed)
        self.assertIn('no audio from the stream for 25 s', logs.output[0])

    def test_the_watcher_stops_with_its_ffmpeg_or_the_stream(self):
        clock = Clock()
        stream = self.stream(clock)
        ended = FakeProc()
        ended.killed = True
        self.assertFalse(stream.watch_stall(ended))
        stream.stopping.set()
        self.assertFalse(stream.watch_stall(FakeProc()))

    def test_ffmpeg_gives_up_on_a_connection_that_sends_nothing(self):
        args = FfmpegCommand.args('ff', 'http://s', 128)
        self.assertEqual(args[args.index('-rw_timeout') + 1], '15000000')
        self.assertLess(args.index('-rw_timeout'), args.index('-i'), 'an input option goes before the input')


class LogFileTest(unittest.TestCase):
    def test_lines_land_in_the_file_with_the_time_and_survive_reopening(self):
        logger = logging.getLogger('stagebot.test-log-file')
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        with tempfile.TemporaryDirectory() as d:
            log_file = LogFile(Path(d) / 'logs')
            self.assertTrue(log_file.attach(logger))
            logger.info('[player] opening the stream')
            logger.debug('discord chatter')
            log_file.detach(logger)
            again = LogFile(Path(d) / 'logs')
            again.attach(logger)
            logger.warning('[player] no audio from the stream')
            again.detach(logger)
            text = (Path(d) / 'logs' / 'stagebot.log').read_text(encoding='utf-8')
        lines = text.splitlines()
        self.assertEqual(len(lines), 2, 'debug lines stay out; the file is added to, not replaced')
        self.assertRegex(lines[0], r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC INFO +\[player\] opening the stream$')
        self.assertIn('WARNING', lines[1])

    def test_rotates_instead_of_growing(self):
        logger = logging.getLogger('stagebot.test-rotate')
        logger.propagate = False
        logger.setLevel(logging.INFO)
        with tempfile.TemporaryDirectory() as d:
            log_file = LogFile(Path(d), max_bytes=200, keep=2)
            log_file.attach(logger)
            for i in range(50):
                logger.info(f'line {i} ' + 'x' * 40)
            log_file.detach(logger)
            names = sorted(p.name for p in Path(d).iterdir())
        self.assertEqual(names, ['stagebot.log', 'stagebot.log.1', 'stagebot.log.2'])

    def test_a_folder_it_cannot_write_is_said_and_the_bot_runs_on(self):
        with tempfile.TemporaryDirectory() as d:
            blocker = Path(d) / 'logs'
            blocker.write_text('a file where the folder should be')
            self.assertFalse(LogFile(blocker).attach(logging.getLogger('stagebot.test-blocked')))



if __name__ == '__main__':
    unittest.main()
