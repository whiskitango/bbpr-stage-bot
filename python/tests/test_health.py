import unittest

from stagebot.connection_health import ConnectionHealth


class ConnectionHealthTest(unittest.TestCase):
    def test_waits_out_a_short_reconnect(self):
        h = ConnectionHealth(patience=3)
        self.assertEqual([h.needs_rejoin(False), h.needs_rejoin(False), h.needs_rejoin(True)], [False, False, False])
        self.assertEqual([h.needs_rejoin(False), h.needs_rejoin(False)], [False, False])

    def test_rejoins_after_a_long_drop_or_when_discord_py_gave_up(self):
        h = ConnectionHealth(patience=3)
        self.assertEqual([h.needs_rejoin(False) for _ in range(3)], [False, False, True])
        self.assertTrue(ConnectionHealth().needs_rejoin(False, given_up=True))


if __name__ == '__main__':
    unittest.main()
