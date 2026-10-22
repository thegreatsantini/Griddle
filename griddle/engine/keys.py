"""Non-blocking single-key reads on Mac, Linux, Windows, and over SSH."""
from __future__ import annotations

import os
import sys


class KeyReader:
    def __init__(self) -> None:
        self._fd = None
        self._old = None

    def __enter__(self) -> "KeyReader":
        if os.name != "nt" and sys.stdin.isatty():
            import termios
            import tty
            self._fd = sys.stdin.fileno()
            self._old = termios.tcgetattr(self._fd)
            tty.setcbreak(self._fd)          # keys arrive instantly, Ctrl+C still works
        return self

    def __exit__(self, *exc) -> None:
        if self._old is not None:
            import termios
            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)

    def read(self) -> str | None:
        """One pending key (lowercased), or None. Never blocks."""
        if os.name == "nt":
            import msvcrt
            if msvcrt.kbhit():
                return msvcrt.getwch().lower()
            return None
        if self._fd is None:
            return None
        import select
        if select.select([sys.stdin], [], [], 0)[0]:
            return os.read(self._fd, 1).decode(errors="ignore").lower() or None
        return None
