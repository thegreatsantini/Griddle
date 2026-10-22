"""griddle sim | run

    python -m griddle sim my_auto.py               laptop: ASCII field
    python -m griddle sim my_auto.py --color red   pretend a red cube was shown
    python -m griddle sim my_auto.py --auto-only   just the 30s auto
    python -m griddle sim my_auto.py --speed 3     3x faster
    python -m griddle run my_auto.py               on Watney: the real robot
    python -m griddle run my_auto.py --color red   referee override if the camera can't tell
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

from griddle.engine import match


def load_student(path: str):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"Can't find {path}")
    spec = importlib.util.spec_from_file_location(p.stem, p)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(p.parent.resolve()))
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise SystemExit(f"{path} has an error before the match even starts:\n  {type(e).__name__}: {e}")
    if not hasattr(module, "autonomous_periodic"):
        print(f"heads up: {p.name} has no autonomous_periodic(bot), so auto will just sit still")
    return module


class LogTail:
    """Catches print() from student code so the field redraw doesn't erase it."""

    def __init__(self, real, keep: int = 6) -> None:
        self.real, self.keep, self.lines, self._partial = real, keep, [], ""

    def write(self, s: str) -> int:
        self._partial += s
        *done, self._partial = self._partial.split("\n")
        self.lines = (self.lines + done)[-self.keep:]
        return len(s)

    def flush(self) -> None:
        pass


def sim_screen(backend, tail: LogTail, real_out, title: str):
    first = [True]

    def draw(state: match.MatchState) -> None:
        out = []
        if first[0]:
            out.append("\x1b[2J")
            first[0] = False
        out.append("\x1b[H")
        left = max(0.0, state.length - state.time)
        header = f" GRIDDLE SIM  {title}   {state.period}  {left:5.1f}s left   drawn color: {backend.shown_color.upper()}"
        lines = [header] + backend.render() + [backend.status(), state.message, "", "--- log ---"]
        while backend.events:
            print(f"[{state.period.lower()} {state.time:4.1f}s] {backend.events.pop(0)}")
        lines += tail.lines + [""] * (tail.keep - len(tail.lines))
        out.extend(line + "\x1b[K\n" for line in lines)
        real_out.write("".join(out))
        real_out.flush()

    return draw


def run_screen():
    last = [None]

    def draw(state: match.MatchState) -> None:
        key = (state.period, int(state.time) // 5)
        if key != last[0]:
            last[0] = key
            left = max(0.0, state.length - state.time)
            print(f"[{state.period}] {left:5.1f}s left  {state.message}")

    return draw


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="griddle", description="Run a Griddle robot file.")
    ap.add_argument("mode", choices=["sim", "run"])
    ap.add_argument("file", help="your robot code, e.g. starter/starter_auto.py")
    ap.add_argument("--color", help="the drawn color (sim) or a referee override (run)")
    ap.add_argument("--auto-only", action="store_true", help="skip teleop")
    ap.add_argument("--speed", type=float, default=1.0, help="sim only: 2 = double speed")
    ap.add_argument("--seed", type=int, help="sim only: repeatable random color draw")
    ap.add_argument("--no-color", action="store_true", help="plain text, no ANSI colors")
    args = ap.parse_args(argv)

    student = load_student(args.file)
    teleop = 0.0 if args.auto_only else match.TELEOP_SECONDS

    if args.mode == "sim":
        from griddle.backends.sim import SimBackend
        if os.name == "nt":
            os.system("")  # turns on ANSI escape codes in Windows terminals
        backend = SimBackend(shown_color=args.color, seed=args.seed, color=not args.no_color)
        real_out = sys.stdout
        tail = LogTail(real_out)
        sys.stdout = tail
        try:
            state = match.run_match(backend, student, teleop_seconds=teleop, speed=args.speed,
                                    on_frame=sim_screen(backend, tail, real_out, Path(args.file).name))
        finally:
            sys.stdout = real_out
        n, good = backend.score()
        print(f"\n{state.message}  Cubes in goals: {n}  ({good} in the right goal)")
    else:
        from griddle.backends.masterpi import MasterPiBackend
        backend = MasterPiBackend(shown_color=args.color)
        state = match.run_match(backend, student, teleop_seconds=teleop, gate=True, on_frame=run_screen())
        print(state.message)


if __name__ == "__main__":
    main()