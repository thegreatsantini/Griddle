from __future__ import annotations
from typing import Callable

from griddle.backends.base import Backend, Cube


class Bot:
    def __init__(self, backend: Backend) -> None:
        self._backend = backend
        self._warnings = {}
        self._clock: Callable[[], float] = lambda: 0.0

    @property
    def busy(self) -> bool:
        """True while a grab or release is still finishing."""
        return self._backend.busy

    @property
    def time(self) -> float:
        """Seconds since the current period (auto or teleop) started."""
        return self._clock()

    def drive(self, fwd: float, turn: float) -> None:
        """Tank drive. fwd and turn both clamp to -1.0 .. 1.0.

        fwd > 0 drives forward. turn > 0 turns right.
        """
        clamped_fwd = max(-1, min(1, fwd))
        clamped_turn = max(-1, min(1, turn))
        if clamped_fwd != fwd:
            self._warn_once("drive_fwd", f"drive() fwd clamped: {fwd} -> {clamped_fwd}")
        if clamped_turn != turn:
            self._warn_once("drive_turn", f"drive() turn clamped: {turn} -> {clamped_turn}")
        self._backend.drive(clamped_fwd, clamped_turn)

    def stop(self) -> None:
        """Same as drive(0, 0)."""
        self._backend.drive(0, 0)

    def grab(self) -> None:
        """Close the gripper. Returns immediately; check `busy`."""
        self._backend.grab()

    def release(self) -> None:
        """Open the gripper. Returns immediately; check `busy`."""
        self._backend.release()

    def find_cube(self, color: str) -> Cube | None:
        """Look for a cube of `color`.

        Returns None if not visible, else an object with
        `x_offset` (-1 left .. 1 right) and `size` (bigger = closer).
        Raises ValueError on a bad color.
        """
        return self._backend.find_cube(color)

    def detect_shown_color(self) -> str:
        """Read the color of a cube held up to the camera ("unknown" if unsure)."""
        return self._backend.detect_shown_color()

    # --- engine-only ---

    def _attach_clock(self, clock: Callable[[], float]) -> None:
        """The engine hands Bot its period timer. Private."""
        self._clock = clock

    def _warn_once(self, key: str, message: str) -> None:
        """Emit `message` the first time `key` is seen. Private."""
        if key not in self._warnings:
            print(message)
            self._warnings[key] = message
