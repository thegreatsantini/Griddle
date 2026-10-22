"""MasterPiBackend: the real Watney. Runs ON the Pi.

Drive comes straight from piground.py (verified motor map).
The gripper and vision need calibration - see the CALIBRATE blocks.
"""
from __future__ import annotations

import threading
import time

from griddle.backends.base import COLORS, Backend, Cube, validate_color

# ===================== DRIVE (verified via piground) =====================
MAX_DUTY = 60           # fwd = 1.0 -> 60% duty. Same cap as piground.

# ===================== GRIPPER / ARM - CALIBRATE =====================
# Find real numbers with:  python3 tools/servo_tune.py   (on Watney)
# PWM servo pulses, 500..2500. Servo 1 is the claw on the MasterPi.
CLAW_SERVO = 1
CLAW_OPEN = 1500        # CALIBRATE
CLAW_CLOSED = 1950      # CALIBRATE - closed on a cube, not crushing it

# Arm poses. Leave ARM_CALIBRATED = False until you have real numbers;
# then grab/release only move the claw and never swing the arm into the chassis.
ARM_CALIBRATED = False
ARM_DOWN = {3: 1500, 4: 1500, 5: 1500}   # CALIBRATE: claw at cube height
ARM_UP = {3: 1500, 4: 1500, 5: 1500}     # CALIBRATE: cube lifted off the floor
ARM_MOVE_TIME = 0.8
CLAW_MOVE_TIME = 0.5

# ===================== VISION - CALIBRATE =====================
CAMERA_INDEX = 0
FRAME_W, FRAME_H = 320, 240
MIN_AREA = 150          # px at 320x240; smaller blobs are noise
SHOWN_MIN_FRACTION = 0.08
# HSV ranges (OpenCV: H 0-180). Red wraps around, so it gets two.
HSV_RANGES = {
    "red":   [((0, 120, 70), (10, 255, 255)), ((170, 120, 70), (180, 255, 255))],
    "green": [((40, 80, 50), (85, 255, 255))],
    "blue":  [((95, 120, 50), (130, 255, 255))],
}


class MasterPiBackend(Backend):
    def __init__(self, shown_color: str | None = None) -> None:
        # shown_color: referee override, used if the camera can't decide.
        self._override = validate_color(shown_color) if shown_color else None
        self._board = None
        self._camera: _Camera | None = None
        self._steps: list[tuple[dict[int, int], float]] = []
        self._step_left = 0.0
        self._warned: set[str] = set()

    # --- lifecycle ---

    def start(self) -> None:
        try:
            from common.ros_robot_controller_sdk import Board
        except ImportError as e:
            raise SystemExit(
                "Can't import the Hiwonder SDK. `griddle run` only works on Watney.\n"
                "On a laptop, use `griddle sim` instead."
            ) from e
        self._board = Board()
        self.stop()
        try:
            self._camera = _Camera(CAMERA_INDEX)
        except Exception as e:  # camera is optional; driving is not
            self._warn("cam", f"[griddle] camera unavailable ({e}). find_cube() will return None.")

    def shutdown(self) -> None:
        self.stop()
        if self._camera:
            self._camera.close()
            self._camera = None

    # --- engine ---

    def stop(self) -> None:
        try:
            if self._board:
                self._board.set_motor_duty([[1, 0], [2, 0], [3, 0], [4, 0]])
        except Exception:
            pass  # never raises

    def tick(self, dt: float) -> None:
        if not self._steps and self._step_left <= 0:
            return
        self._step_left -= dt
        if self._step_left <= 0:
            if self._steps:
                self._run_step(*self._steps.pop(0))
            else:
                self._step_left = 0

    # --- Bot ---

    @property
    def busy(self) -> bool:
        return bool(self._steps) or self._step_left > 0

    def drive(self, fwd: float, turn: float) -> None:
        # Positive turn = right: left side speeds up, right side slows down.
        left, right = fwd + turn, fwd - turn
        biggest = max(1.0, abs(left), abs(right))   # keep the ratio, cap at 1
        left = int(left / biggest * MAX_DUTY)
        right = int(right / biggest * MAX_DUTY)
        self._board.set_motor_duty([
            [1, right], [2, right],     # right side: FR, BR
            [3, -left], [4, -left],     # left side: FL, BL (mirrored mount)
        ])

    def grab(self) -> None:
        if self.busy:
            return
        steps = [({CLAW_SERVO: CLAW_CLOSED}, CLAW_MOVE_TIME)]
        if ARM_CALIBRATED:
            steps.append((ARM_UP, ARM_MOVE_TIME))
        self._start(steps)

    def release(self) -> None:
        if self.busy:
            return
        steps = []
        if ARM_CALIBRATED:
            steps.append((ARM_DOWN, ARM_MOVE_TIME))
        steps.append(({CLAW_SERVO: CLAW_OPEN}, CLAW_MOVE_TIME))
        self._start(steps)

    def find_cube(self, color: str) -> Cube | None:
        color = validate_color(color)
        frame = self._frame()
        if frame is None:
            return None
        import cv2
        mask = _mask(frame, color)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        biggest = max(contours, key=cv2.contourArea)
        if cv2.contourArea(biggest) < MIN_AREA:
            return None
        x, y, w, h = cv2.boundingRect(biggest)
        cx = x + w / 2
        return Cube(x_offset=round((cx - FRAME_W / 2) / (FRAME_W / 2), 3), size=round(w / FRAME_W, 4))

    def detect_shown_color(self) -> str:
        if self._override:
            return self._override
        frame = self._frame()
        if frame is None:
            return "unknown"
        # Only look at the middle of the frame, where a held-up cube is.
        h, w = frame.shape[:2]
        roi = frame[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
        counts = {c: int((_mask(roi, c) > 0).sum()) for c in COLORS}
        best = max(counts, key=counts.get)
        if counts[best] < SHOWN_MIN_FRACTION * roi.shape[0] * roi.shape[1]:
            return "unknown"
        return best

    # --- private ---

    def _start(self, steps: list[tuple[dict[int, int], float]]) -> None:
        self._steps = list(steps)
        self._run_step(*self._steps.pop(0))

    def _run_step(self, pose: dict[int, int], seconds: float) -> None:
        self._board.pwm_servo_set_position(seconds, [[sid, pulse] for sid, pulse in pose.items()])
        self._step_left = seconds

    def _frame(self):
        if not self._camera:
            return None
        frame = self._camera.latest()
        if frame is None:
            self._warn("noframe", "[griddle] camera has no frame yet")
        return frame

    def _warn(self, key: str, msg: str) -> None:
        if key not in self._warned:
            print(msg)
            self._warned.add(key)


def _mask(frame_bgr, color: str):
    import cv2
    import numpy as np
    hsv = cv2.cvtColor(cv2.GaussianBlur(frame_bgr, (5, 5), 0), cv2.COLOR_BGR2HSV)
    mask = None
    for lo, hi in HSV_RANGES[color]:
        m = cv2.inRange(hsv, np.array(lo), np.array(hi))
        mask = m if mask is None else cv2.bitwise_or(mask, m)
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)


class _Camera:
    """Grabs frames on a background thread so find_cube() never blocks the 20Hz loop."""

    def __init__(self, index: int) -> None:
        import cv2
        self._cv2 = cv2
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise RuntimeError(f"can't open camera {index} (is the Hiwonder app holding it?)")
        self._frame = None
        self._lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            ok, frame = self._cap.read()
            if ok:
                small = self._cv2.resize(frame, (FRAME_W, FRAME_H))
                with self._lock:
                    self._frame = small
            else:
                time.sleep(0.05)

    def latest(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=1)
        self._cap.release()
