"""Keeps the station playing, once, for every server at the same time.

One ffmpeg reads the MP3 stream and re-encodes it to Opus in Ogg; a reader
thread splits that into 20 ms Opus packets and hands each one to every
listener. Each voice connection plays its own RadioListener, so all servers
hear the same live audio and AzuraCast counts one listener, however many
servers there are. If the stream ends, it is reopened after a backoff,
forever, and listeners hear silence in between instead of being stopped."""

from __future__ import annotations

import collections
import logging
import subprocess
import threading
from typing import Deque, List, Optional, Set

import discord
from discord.oggparse import OggStream

from .backoff import Backoff
from .volume import Volume

log = logging.getLogger('stagebot')

SILENCE = b'\xf8\xff\xfe'          # one Opus frame of silence
HEADERS = (b'OpusHead', b'OpusTags')
MAX_QUEUE = 150                    # 3 s; older packets are dropped to stay live


class RadioListener(discord.AudioSource):
    """What one voice connection plays: the station's packets as they come,
    or silence while the stream is reopening. It never ends by itself."""

    def __init__(self, stream: 'RadioStream'):
        self.stream = stream
        self.queue: Deque[bytes] = collections.deque(maxlen=MAX_QUEUE)
        self.packets = 0
        self.silent = 0

    def is_opus(self) -> bool:
        return True

    def feed(self, packet: bytes) -> None:
        self.queue.append(packet)

    def read(self) -> bytes:
        try:
            packet = self.queue.popleft()
            self.packets += 1
            return packet
        except IndexError:
            self.silent += 1
            return SILENCE

    def cleanup(self) -> None:
        self.stream.forget(self)


class FfmpegCommand:
    """The ffmpeg arguments that turn the station's stream into Ogg Opus at
    the bot's volume. Its reconnect flags ride out short network blips
    without a gap."""

    @staticmethod
    def args(ffmpeg: str, url: str, bitrate: int, volume: Optional[Volume] = None) -> List[str]:
        volume = volume or Volume()
        return [
            ffmpeg, '-hide_banner', '-loglevel', 'error',
            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_on_network_error', '1',
            '-reconnect_delay_max', '5',
            '-i', url,
            '-vn', '-af', volume.ffmpeg_filter(),
            '-c:a', 'libopus', '-b:a', f'{bitrate}k', '-ar', '48000', '-ac', '2',
            '-frame_duration', '20', '-application', 'audio',
            # Small Ogg pages: by default ffmpeg writes about a second at a time.
            '-f', 'ogg', '-page_duration', '20000', '-flush_packets', '1', 'pipe:1',
        ]


class RadioStream:
    def __init__(self, url: str, ffmpeg: str = 'ffmpeg', bitrate: int = 128, backoff: Optional[Backoff] = None,
                 volume: Optional[Volume] = None):
        self.url = url
        self.ffmpeg = ffmpeg
        self.bitrate = bitrate
        self.volume = volume or Volume()
        self.backoff = backoff or Backoff()
        self.listeners: Set[RadioListener] = set()
        self.lock = threading.Lock()
        self.proc: Optional[subprocess.Popen] = None
        self.thread: Optional[threading.Thread] = None
        self.stopping = threading.Event()

    def listen(self) -> RadioListener:
        listener = RadioListener(self)
        with self.lock:
            self.listeners.add(listener)
        return listener

    def forget(self, listener: RadioListener) -> None:
        with self.lock:
            self.listeners.discard(listener)

    def broadcast(self, packet: bytes) -> None:
        with self.lock:
            listeners = list(self.listeners)
        for listener in listeners:
            listener.feed(packet)

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stopping.clear()
        self.thread = threading.Thread(target=self.run, name='radio-stream', daemon=True)
        self.thread.start()

    def run(self) -> None:
        while not self.stopping.is_set():
            self.play_once()
            if self.stopping.is_set():
                break
            wait = self.backoff.next()
            log.warning(f'[player] stream ended; reopening in {round(wait)} s')
            self.stopping.wait(wait)

    def play_once(self) -> None:
        log.info(f'[player] opening the stream at {self.volume.percent}% volume')
        self.backoff.started()
        try:
            self.proc = subprocess.Popen(
                FfmpegCommand.args(self.ffmpeg, self.url, self.bitrate, self.volume),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except OSError as err:
            log.error(f'[ffmpeg] could not start {self.ffmpeg}: {err}')
            return
        threading.Thread(target=self.log_errors, args=(self.proc,), daemon=True).start()
        try:
            for packet in OggStream(self.proc.stdout).iter_packets():
                if self.stopping.is_set():
                    break
                if packet.startswith(HEADERS):
                    continue
                self.broadcast(packet)
        except Exception as err:
            log.warning(f'[player] {err}')
        finally:
            self.close()

    @staticmethod
    def log_errors(proc: subprocess.Popen) -> None:
        for line in proc.stderr:
            text = line.decode(errors='replace').strip()
            if text:
                log.warning(f'[ffmpeg] {text}')

    def close(self) -> None:
        proc, self.proc = self.proc, None
        if proc and proc.poll() is None:
            proc.kill()

    def stop(self) -> None:
        self.stopping.set()
        self.close()
