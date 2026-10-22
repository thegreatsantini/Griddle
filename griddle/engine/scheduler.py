"""Fixed-rate timing. The engine owns time so student code never sleeps."""
from __future__ import annotations

import time


class Rate:
    """Run something `hz` times per (sim) second.

    speed = 1.0 is real time, 2.0 is double speed, 0 is as fast as possible.
    Each call to wait() returns how many fixed steps are due right now, so a
    slow frame catches up instead of making the robot drive farther per step.
    """

    def __init__(self, hz: float, speed: float = 1.0) -> None:
        self.dt = 1.0 / hz
        self.speed = speed
        self._start = time.monotonic()
        self._steps_done = 0

    def wait(self) -> int:
        if self.speed <= 0:
            self._steps_done += 1
            return 1
        while True:
            elapsed_sim = (time.monotonic() - self._start) * self.speed
            due = int(elapsed_sim / self.dt) - self._steps_done
            if due > 0:
                due = min(due, 10)          # never "teleport" after a long hiccup
                self._steps_done += due
                return due
            time.sleep(self.dt / self.speed / 4)
