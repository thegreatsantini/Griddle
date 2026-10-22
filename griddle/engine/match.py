"""One match: 30s autonomous, then 2 min teleop. The engine owns time and safety.

Student files can define any of:
    autonomous_init(bot)
    autonomous_periodic(bot)        called 20x per second during auto
    teleop_init(bot)
    teleop_periodic(bot, key)       key = last key pressed this tick, or None

If a student file has no teleop_periodic, the built-in driver controls run.
If student code crashes, the robot stops and the error is shown. During
teleop a crash falls back to built-in driver controls so the run isn't lost.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from types import ModuleType
from typing import Callable

from griddle.api.bot import Bot
from griddle.backends.base import Backend
from griddle.engine.keys import KeyReader
from griddle.engine.scheduler import Rate

HZ = 20
AUTO_SECONDS = 30.0
TELEOP_SECONDS = 120.0
QUIT_KEYS = ("q", "\x1b")

DRIVE_HELP = "W/S fwd/back  A/D turn  SPACE stop  G grab  R release  +/- speed  Q quit"


class MatchAborted(Exception):
    pass


@dataclass
class MatchState:
    period: str = "READY"           # READY, AUTO, TELEOP, DONE
    time: float = 0.0
    length: float = 0.0
    message: str = ""
    log: list[str] = field(default_factory=list)


class DefaultDriver:
    """piground-style tap-to-move controls. Keys latch until you press another."""

    def __init__(self) -> None:
        self.speed = 0.7
        self.turn_scale = 0.75

    def __call__(self, bot: Bot, key: str | None) -> None:
        if key is None:
            return
        turn = self.speed * self.turn_scale
        if key == "w":
            bot.drive(self.speed, 0)
        elif key == "s":
            bot.drive(-self.speed, 0)
        elif key == "a":
            bot.drive(0, -turn)
        elif key == "d":
            bot.drive(0, turn)
        elif key == " ":
            bot.drive(0, 0)
        elif key == "g":
            bot.grab()
        elif key == "r":
            bot.release()
        elif key in ("+", "="):
            self.speed = min(1.0, round(self.speed + 0.1, 1))
            print(f"speed -> {self.speed}")
        elif key in ("-", "_"):
            self.speed = max(0.2, round(self.speed - 0.1, 1))
            print(f"speed -> {self.speed}")


def run_match(
    backend: Backend,
    student: ModuleType,
    *,
    auto_seconds: float = AUTO_SECONDS,
    teleop_seconds: float = TELEOP_SECONDS,
    speed: float = 1.0,
    gate: bool = False,
    on_frame: Callable[[MatchState], None] | None = None,
) -> MatchState:
    """Run a full match. Motors are stopped on every way out of here."""
    bot = Bot(backend)
    state = MatchState()
    frame = on_frame or (lambda s: None)

    backend.start()
    try:
        with KeyReader() as keys:
            if gate:
                _wait_for_key(keys, state, frame, "Hold the color cube up to the camera, then press ENTER to start AUTO")
            _run_period("AUTO", bot, backend, student, None, keys, state, frame, auto_seconds, speed)
            backend.stop()
            if teleop_seconds > 0:
                if gate:
                    _wait_for_key(keys, state, frame, "AUTO done. Driver ready? Press ENTER to start TELEOP")
                driver = getattr(student, "teleop_periodic", None)
                _run_period("TELEOP", bot, backend, student, driver, keys, state, frame, teleop_seconds, speed)
        state.period, state.message = "DONE", "Match over."
    except (KeyboardInterrupt, MatchAborted):
        state.period, state.message = "DONE", "Match stopped early."
    finally:
        backend.stop()
        backend.shutdown()
    frame(state)
    return state


def _run_period(name, bot, backend, student, teleop_fn, keys, state, frame, length, speed) -> None:
    state.period, state.time, state.length = name, 0.0, length
    state.message = DRIVE_HELP if name == "TELEOP" else "Autonomous - hands off! (Q to abort)"
    bot._attach_clock(lambda: state.time)
    backend.stop()

    prefix = "autonomous" if name == "AUTO" else "teleop"
    alive = _call(getattr(student, f"{prefix}_init", None), (bot,), state, name)

    if name == "AUTO":
        periodic, args_with_key = getattr(student, "autonomous_periodic", None), False
    else:
        periodic, args_with_key = teleop_fn or DefaultDriver(), True
    fallback = DefaultDriver()

    rate = Rate(HZ, speed)
    while state.time < length:
        steps = rate.wait()
        key = keys.read()
        if key in QUIT_KEYS:
            raise MatchAborted
        for i in range(steps):
            k = key if i == 0 else None
            if alive and periodic is not None:
                args = (bot, k) if args_with_key else (bot,)
                alive = _call(periodic, args, state, name)
                if not alive:
                    backend.stop()
                    if name == "TELEOP":
                        state.message = "Your teleop crashed - built-in controls take over. " + DRIVE_HELP
            elif name == "TELEOP":
                fallback(bot, k)
            backend.tick(rate.dt)
            state.time = min(length, state.time + rate.dt)
            if state.time >= length:
                break
        frame(state)
    backend.stop()


def _call(fn, args, state: MatchState, period: str) -> bool:
    """Run student code. Returns False if it crashed."""
    if fn is None:
        return True
    try:
        fn(*args)
        return True
    except (KeyboardInterrupt, MatchAborted):
        raise
    except Exception:
        tb = traceback.format_exc().rstrip().splitlines()
        print(f"!!! your code crashed during {period} at {state.time:.1f}s - robot stopped")
        for line in tb[-4:]:
            print("    " + line)
        return False


def _wait_for_key(keys: KeyReader, state: MatchState, frame, message: str) -> None:
    import time
    state.period, state.message = "READY", message
    frame(state)
    while True:
        k = keys.read()
        if k in ("\n", "\r", " "):
            return
        if k in QUIT_KEYS:
            raise MatchAborted
        time.sleep(0.05)
