"""The hardware contract.

Every backend implements this. Nothing in this file knows about the
student API, the engine, or the CLI - dependencies point inward only.

If a method here can only be done by one backend, it does not belong
in this file.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass


# Every color a cube can be. Both backends validate against this.
COLORS = ("red", "green", "blue")


def validate_color(color: str) -> str:
    """Return `color` lowercased, or raise ValueError with a kid-readable message."""
    if not isinstance(color, str) or color.lower() not in COLORS:
        raise ValueError(f"unknown color {color!r} - pick one of {', '.join(COLORS)}")
    return color.lower()


@dataclass
class Cube:
    """A cube the camera can see.

    x_offset: -1.0 (hard left) to 1.0 (hard right), 0.0 dead center
    size:     apparent size in the frame; bigger means closer
    """

    x_offset: float
    size: float


class Backend(ABC):
    """What a robot has to be able to do to run Griddle."""

    # --- lifecycle: the CLI calls these ---

    @abstractmethod
    def start(self) -> None:
        """Open serial, camera, whatever this backend needs."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Release everything. Safe to call twice."""
        ...

    # --- the engine calls these ---

    @abstractmethod
    def tick(self, dt: float) -> None:
        """Advance one step. `dt` is seconds since the last tick."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Motors to zero, now. Dead-man switch. Never raises."""
        ...

    # --- Bot calls these ---

    @property
    @abstractmethod
    def busy(self) -> bool:
        """True while a grab or release is still finishing."""
        ...

    @abstractmethod
    def drive(self, fwd: float, turn: float) -> None:
        """Tank drive. Inputs are already clamped to -1.0 .. 1.0."""
        ...

    @abstractmethod
    def grab(self) -> None:
        """Start closing the gripper. Returns immediately."""
        ...

    @abstractmethod
    def release(self) -> None:
        """Start opening the gripper. Returns immediately."""
        ...

    @abstractmethod
    def find_cube(self, color: str) -> Cube | None:
        """Look for a cube of `color`.

        Returns None if not visible. Raises ValueError on a bad color.
        """
        ...

    @abstractmethod
    def detect_shown_color(self) -> str:
        """Read the color of a cube held up to the camera.

        Returns one of COLORS, or "unknown" if nothing is clear.
        """
        ...

    @abstractmethod
    def floor_color(self) -> str | None:
        """Color of the goal square right in front of the claw, or None."""
        ...