"""Starts the Stage bot. Settings come from the environment, or from the .env
file at the top of the repo (see .env.example)."""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from stagebot.config import ROOT, Config
from stagebot.env_file import EnvFile
from stagebot.instance_lock import InstanceLock
from stagebot.stage_bot import StageBot


class Launcher:
    def __init__(self):
        self.lock = InstanceLock()
        self.bot: StageBot = None

    @staticmethod
    def setup_logging(debug: bool) -> None:
        logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)
        logging.getLogger('discord').setLevel(logging.DEBUG if debug else logging.WARNING)
        if debug:
            logging.getLogger('discord.gateway').setLevel(logging.INFO)
            logging.getLogger('discord.http').setLevel(logging.INFO)

    def run(self) -> int:
        EnvFile(ROOT / '.env').load()
        config = Config.from_env()
        missing = config.missing()
        if missing:
            print(f"Missing settings: {', '.join(missing)}. Copy .env.example to .env and fill them in.", file=sys.stderr)
            return 1
        running = self.lock.acquire()
        if running:
            print(f'The bot is already running (process {running}). Stop that one first.', file=sys.stderr)
            return 1
        self.setup_logging(config.voice_debug)
        try:
            asyncio.run(self.serve(config))
        except KeyboardInterrupt:
            pass
        finally:
            self.lock.release()
        return 0

    async def serve(self, config: Config) -> None:
        self.bot = StageBot(config)
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.bot.shutdown()))
            except (NotImplementedError, RuntimeError):
                pass   # Windows: Ctrl+C arrives as KeyboardInterrupt instead
        try:
            async with self.bot:
                await self.bot.start(config.token)
        except (KeyboardInterrupt, asyncio.CancelledError):
            await self.bot.shutdown()
        except Exception as err:
            print(f'Could not log in to Discord: {err}', file=sys.stderr)
            raise


if __name__ == '__main__':
    sys.exit(Launcher().run())
