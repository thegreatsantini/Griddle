"""SimBackend: a top-down 2D sim of the 6x6 field, drawn in ASCII.

Coordinates are feet. (0, 0) is the bottom-left corner, x goes right,
y goes up. Heading is degrees: 0 = facing right, 90 = facing up.

Everything below the CONSTANTS line is physics. Everything above it is
the field and the robot, and should be edited to match the real mat.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from griddle.backends.base import COLORS, Backend, Cube, validate_color

# ===================== CONSTANTS - tune these to match reality =====================

FIELD_SIZE = 6.0        # feet, square
MAX_SPEED = 1.5         # feet per second at fwd = 1.0   (MEASURE on Watney)
MAX_TURN_RATE = 3.14    # radians per second at turn = 1.0 (MEASURE on Watney)
GRAB_TIME = 1.0         # seconds for a grab or release to finish

# Goals: the painted squares in the top row of tiles, left to right.
# Each tile is 2 ft; the painted square is inset GOAL_INSET from the tile edges.
GOAL_ORDER = ["red", "green", "blue"]
TILE = 2.0
GOAL_INSET = 0.25       # ~3" border around each painted square (MEASURE)

# Robot geometry
ROBOT_RADIUS = 0.35     # keeps the robot body on the field
CLAW_REACH = 0.45       # center of robot -> center of claw
GRAB_RADIUS = 0.25      # a cube this close to the claw gets picked up (3")
CAMERA_FORWARD = 0.2    # camera sits a bit ahead of center
CAMERA_FOV = math.radians(60)
VISION_RANGE = 4.0      # feet; farther cubes are too small to detect
CUBE_WIDTH = 0.125      # feet (1.5")

# Where the robot starts: x, y, heading (degrees). Facing up, lined up with the
# left green spot (x = 32") so the starter is one straight line - no turns.
START_POSE = (32 / 12, 1.0, 90.0)   # y = mat bottom edge -> Watney's center (MEASURE)

# Block line: y = 36". Two blocks per color, each pair under its own goal,
# at tile center +/- 4" (so 8" apart in a pair, 16" between pairs).
BLOCK_Y = 36
BLOCK_X = [8, 16, 32, 40, 56, 64]     # inches from the left edge (MEASURE)

# Which color sits on each spot, left to right. Pick with LAYOUT.
LAYOUTS = {
    "L1": ["red", "red", "green", "green", "blue", "blue"],   # color under its goal
    "L2": ["blue", "blue", "green", "red", "red", "green"],   # fixed mix; spot 3 stays green for the starter
    "L3": None,                                               # shuffled each reset (--seed)
}
LAYOUT = "L1"

# ===================================================================================

ANSI = {"red": "\x1b[91m", "green": "\x1b[92m", "blue": "\x1b[94m", "dim": "\x1b[2m", "bold": "\x1b[1m"}
RESET = "\x1b[0m"
ARROWS = ["→", "↗", "↑", "↖", "←", "↙", "↓", "↘"]

COLS_PER_FT = 8         # terminal cells are ~2x taller than wide,
ROWS_PER_FT = 4         # so 8x4 per foot looks square


@dataclass
class SimCube:
    color: str
    x: float
    y: float
    held: bool = False


class SimBackend(Backend):
    def __init__(self, shown_color: str | None = None, seed: int | None = None, color: bool = True) -> None:
        self._rng = random.Random(seed)
        self.shown_color = validate_color(shown_color) if shown_color else self._rng.choice(COLORS)
        self._use_color = color
        self.reset()

    # --- lifecycle ---

    def reset(self) -> None:
        x, y, h = START_POSE
        self.x, self.y, self.heading = x, y, math.radians(h)
        self.cubes = [SimCube(c, x / 12, BLOCK_Y / 12) for c, x in zip(self._layout(), BLOCK_X)]
        self._fwd = 0.0
        self._turn = 0.0
        self._busy_left = 0.0
        self._pending: str | None = None     # "grab" or "release"
        self.held: SimCube | None = None
        self.at_edge = False
        self.events: list[str] = []          # things worth telling the user

    def _layout(self) -> list[str]:
        colors = LAYOUTS[LAYOUT]
        if colors is None:
            colors = [c for c in GOAL_ORDER for _ in range(len(BLOCK_X) // len(GOAL_ORDER))]
            self._rng.shuffle(colors)
        return colors

    def start(self) -> None:
        pass

    def shutdown(self) -> None:
        self.stop()

    # --- engine ---

    def stop(self) -> None:
        self._fwd = 0.0
        self._turn = 0.0

    def tick(self, dt: float) -> None:
        # Drive. Positive turn = clockwise, so it subtracts from heading.
        self.heading -= self._turn * MAX_TURN_RATE * dt
        self.heading = (self.heading + math.pi) % (2 * math.pi) - math.pi
        dist = self._fwd * MAX_SPEED * dt
        nx = self.x + dist * math.cos(self.heading)
        ny = self.y + dist * math.sin(self.heading)
        lo, hi = ROBOT_RADIUS, FIELD_SIZE - ROBOT_RADIUS
        self.at_edge = not (lo <= nx <= hi and lo <= ny <= hi)
        self.x = min(hi, max(lo, nx))
        self.y = min(hi, max(lo, ny))

        # Gripper timing
        if self._busy_left > 0:
            self._busy_left -= dt
            if self._busy_left <= 0:
                self._busy_left = 0
                self._finish_gripper()

        if self.held:
            self.held.x, self.held.y = self.claw

    # --- Bot ---

    @property
    def busy(self) -> bool:
        return self._busy_left > 0

    def drive(self, fwd: float, turn: float) -> None:
        self._fwd = fwd
        self._turn = turn

    def grab(self) -> None:
        if self.busy:
            return
        self._pending = "grab"
        self._busy_left = GRAB_TIME

    def release(self) -> None:
        if self.busy:
            return
        self._pending = "release"
        self._busy_left = GRAB_TIME

    def find_cube(self, color: str) -> Cube | None:
        color = validate_color(color)
        cam_x = self.x + CAMERA_FORWARD * math.cos(self.heading)
        cam_y = self.y + CAMERA_FORWARD * math.sin(self.heading)
        best: Cube | None = None
        for c in self.cubes:
            if c.held or c.color != color:
                continue
            dx, dy = c.x - cam_x, c.y - cam_y
            d = math.hypot(dx, dy)
            if d < 1e-6 or d > VISION_RANGE:
                continue
            bearing = math.atan2(dy, dx) - self.heading
            bearing = (bearing + math.pi) % (2 * math.pi) - math.pi
            if abs(bearing) > CAMERA_FOV / 2:
                continue
            # Same meaning as the real camera: fraction of frame width the cube covers.
            size = min(1.0, (2 * math.atan(CUBE_WIDTH / 2 / d)) / CAMERA_FOV)
            found = Cube(x_offset=round(-bearing / (CAMERA_FOV / 2), 3) + 0.0, size=round(size, 4))
            if best is None or found.size > best.size:
                best = found
        return best

    def detect_shown_color(self) -> str:
        return self.shown_color

    # --- sim-only helpers ---

    @property
    def claw(self) -> tuple[float, float]:
        return (self.x + CLAW_REACH * math.cos(self.heading),
                self.y + CLAW_REACH * math.sin(self.heading))

    def _finish_gripper(self) -> None:
        cx, cy = self.claw
        if self._pending == "grab":
            if self.held:
                self.events.append("grab: already holding a cube")
            else:
                near = [c for c in self.cubes if not c.held and math.hypot(c.x - cx, c.y - cy) <= GRAB_RADIUS]
                if near:
                    cube = min(near, key=lambda c: math.hypot(c.x - cx, c.y - cy))
                    cube.held = True
                    self.held = cube
                    self.events.append(f"grabbed {cube.color}")
                else:
                    self.events.append("grab: missed, nothing under the claw")
        elif self._pending == "release":
            if self.held:
                self.held.held = False
                self.held.x, self.held.y = cx, cy
                g = goal_at(cx, cy)
                if g is None:
                    where = "outside the goals"
                elif g == self.held.color:
                    where = f"in the {g.upper()} goal - correct!"
                else:
                    where = f"in the {g.upper()} goal - WRONG goal"
                self.events.append(f"released {self.held.color} {where}")
                self.held = None
            else:
                self.events.append("release: claw was already empty")
        self._pending = None

    def score(self) -> tuple[int, int]:
        """(cubes in any goal, cubes in their own color's goal)"""
        placed = [(c, goal_at(c.x, c.y)) for c in self.cubes if not c.held]
        scored = [(c, g) for c, g in placed if g is not None]
        return len(scored), sum(c.color == g for c, g in scored)

    # --- drawing ---

    def _paint(self, text: str, color: str) -> str:
        return f"{ANSI[color]}{text}{RESET}" if self._use_color else text

    def render(self) -> list[str]:
        cols = int(FIELD_SIZE * COLS_PER_FT)
        rows = int(FIELD_SIZE * ROWS_PER_FT)
        grid = [[" "] * cols for _ in range(rows)]

        def cell(x: float, y: float) -> tuple[int, int]:
            c = min(cols - 1, max(0, int(x * COLS_PER_FT)))
            r = min(rows - 1, max(0, int((FIELD_SIZE - y) * ROWS_PER_FT)))
            return r, c

        for r in range(rows):
            for c in range(cols):
                x = (c + 0.5) / COLS_PER_FT
                y = FIELD_SIZE - (r + 0.5) / ROWS_PER_FT
                g = goal_at(x, y)
                if g is not None:
                    grid[r][c] = self._paint("·", g)

        for cube in self.cubes:
            if not cube.held:
                r, c = cell(cube.x, cube.y)
                grid[r][c] = self._paint(cube.color[0].upper(), cube.color)

        r, c = cell(self.x, self.y)
        octant = int(round(self.heading / (math.pi / 4))) % 8
        arrow = ARROWS[octant]
        grid[r][c] = self._paint(arrow, self.held.color) if self.held else self._paint(arrow, "bold")

        border = "+" + "-" * cols + "+"
        lines = [border] + ["|" + "".join(row) + "|" for row in grid] + [border]
        return lines

    def status(self) -> str:
        n, match = self.score()
        holding = self.held.color.upper() if self.held else "nothing"
        edge = "  EDGE!" if self.at_edge else ""
        return (f"pos ({self.x:.1f}, {self.y:.1f}) ft  heading {math.degrees(self.heading):+.0f}°  "
                f"holding {holding}  busy {'yes' if self.busy else 'no '}  "
                f"goals {n} ({match} correct){edge}")


def goal_at(x: float, y: float) -> str | None:
    """Color of the goal square at (x, y), or None if it's not in one."""
    y_lo = FIELD_SIZE - TILE + GOAL_INSET
    y_hi = FIELD_SIZE - GOAL_INSET
    if not (y_lo <= y <= y_hi):
        return None
    for i, color in enumerate(GOAL_ORDER):
        if i * TILE + GOAL_INSET <= x <= (i + 1) * TILE - GOAL_INSET:
            return color
    return None