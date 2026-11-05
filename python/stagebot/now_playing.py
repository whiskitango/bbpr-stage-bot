"""Asks AzuraCast what is on air every so often and reports when the song
changes, so the bot's "Listening to" status can follow along. A failed
check is skipped quietly; the music doesn't depend on it."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

import aiohttp

from .live_acts import LiveActs

log = logging.getLogger('stagebot')


class NowPlayingWatch:
    def __init__(self, url: str, on_change: Callable[[str], Awaitable[None]], every: float = 30.0):
        self.url = url
        self.on_change = on_change
        self.every = every
        self.last: Optional[str] = None
        self.task: Optional[asyncio.Task] = None

    @staticmethod
    def song_of(body: dict, acts: Optional[LiveActs] = None) -> str:
        """"Artist - Title" normally; "DJ Whiski - Title" while a DJ is live,
        with the DJ's name spelled as in LiveActs. A DJ whose software sends no
        song details, or only their own name, shows as just their name."""
        acts = acts or LiveActs()
        body = body or {}
        song = (body.get('now_playing') or {}).get('song') or {}
        live = body.get('live') or {}
        raw = live.get('streamer_name') if live.get('is_live') else ''
        if raw and raw.strip():
            dj = acts.name_of(raw)
            title = song.get('title') or song.get('text') or ''
            return f'{dj} - {title}' if title and not acts.same(title, dj) else dj
        if song.get('artist') and song.get('title'):
            return f"{song['artist']} - {song['title']}"
        return song.get('text') or ''

    def start(self) -> None:
        if self.url and not self.task:
            self.task = asyncio.create_task(self.run())

    async def run(self) -> None:
        async with aiohttp.ClientSession(headers={'User-Agent': 'bbpr-stage-bot'}) as http:
            while True:
                await self.check(http)
                await asyncio.sleep(self.every)

    async def check(self, http: aiohttp.ClientSession) -> None:
        try:
            async with http.get(self.url, timeout=aiohttp.ClientTimeout(total=15)) as res:
                if res.status != 200:
                    return
                song = self.song_of(await res.json())
            if not song or song == self.last:
                return
            self.last = song
            await self.on_change(song)
        except Exception as err:  # a missed check is fine; the next one follows
            log.warning(f'[now playing] {err}')

    def stop(self) -> None:
        if self.task:
            self.task.cancel()
        self.task = None
