"""Finds the ffmpeg to decode the stream with. FFMPEG_PATH wins; then the
copy imageio-ffmpeg ships with (installed with the bot); then the Node bot's
ffmpeg-static download; then whatever ffmpeg is on the PATH."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Optional

from .config import ROOT


class FfmpegLocator:
    @staticmethod
    def bundled() -> Optional[str]:
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None

    @classmethod
    def find(cls, env: Optional[Mapping[str, str]] = None) -> str:
        env = os.environ if env is None else env
        if env.get('FFMPEG_PATH'):
            return env['FFMPEG_PATH']
        bundled = cls.bundled()
        if bundled:
            return bundled
        node_copy = ROOT / 'node_modules' / 'ffmpeg-static' / ('ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        if node_copy.exists():
            return str(node_copy)
        return 'ffmpeg'
