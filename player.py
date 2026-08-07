"""Простая обёртка вокруг libmpv (через python-mpv)."""
from __future__ import annotations

import os
import sys
from typing import Callable, Optional


def _libmpv_dir() -> str:
    """Папка, где лежит libmpv-2.dll (рядом с .exe или скриптом)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


# ВАЖНО: PATH правим ДО import mpv, иначе ctypes не найдёт dll.
_DLL_DIR = _libmpv_dir()
os.environ["PATH"] = _DLL_DIR + os.pathsep + os.environ.get("PATH", "")
if hasattr(os, "add_dll_directory"):
    try:
        os.add_dll_directory(_DLL_DIR)
    except Exception:
        pass

import mpv  # noqa: E402


class Player:
    def __init__(self, on_end: Optional[Callable[[], None]] = None):
        self.mpv = mpv.MPV(ytdl=False, video=False, audio_display=False)
        self._on_end = on_end

        @self.mpv.event_callback("end-file")
        def _(ev):  # noqa: ANN001
            # ev.data.reason: 'eof' | 'stop' | 'quit' | 'error' | 'redirect'
            data = getattr(ev, "data", None)
            reason = getattr(data, "reason", data)
            reason_str = str(reason).lower()
            # авто-некст ТОЛЬКО когда трек реально доиграл до конца
            if "eof" in reason_str and self._on_end:
                self._on_end()

    # ---------- управление ----------
    def play(self, url: str) -> None:
        self.mpv.play(url)

    def toggle(self) -> None:
        self.mpv.pause = not self.mpv.pause

    @property
    def paused(self) -> bool:
        return bool(self.mpv.pause)

    def stop(self) -> None:
        self.mpv.command("stop")

    def seek(self, seconds: float) -> None:
        try:
            self.mpv.seek(seconds, reference="absolute")
        except Exception:
            pass

    @property
    def position(self) -> float:
        return float(self.mpv.time_pos or 0.0)

    @property
    def duration(self) -> float:
        return float(self.mpv.duration or 0.0)

    def set_volume(self, v: float) -> None:
        # 0..1 -> 0..100
        self.mpv.volume = max(0, min(100, v * 100))

    def shutdown(self) -> None:
        try:
            self.mpv.terminate()
        except Exception:
            pass
