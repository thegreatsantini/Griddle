
#!/usr/bin/env python3
# coding=utf8
#
# piground.py — simple tank-drive WASD teleop for Watney (MasterPi)
# Normal wheels, tank drive. Tap-to-move over SSH. Runs ON the Pi.
#
# Controls:
#   W = forward      S = back
#   A = turn left    D = turn right
#   SPACE = stop     +/- = speed up/down
#   Q = quit (stops motors first)
#
# Single keypress is read live — no Enter needed. Ctrl+C also stops safely.
#
# Motor map (verified on the box, positive duty):
#   M1 = front right, spins forward
#   M2 = back right,  spins forward
#   M3 = front left,  spins BACKWARD (mirrored mount)
#   M4 = back left,   spins BACKWARD (mirrored mount)
# So the left side gets flipped in tank().

import sys
import termios
import tty
import atexit

from common.ros_robot_controller_sdk import Board

board = Board()

# --- Safety: speed cap and guaranteed stop ---
MAX_SPEED = 60          # hard cap, 0-100 duty. Kids near course = keep it sane.
speed = 40              # starting speed
TURN_SCALE = 0.75       # turns run at 75% of drive speed so it doesn't whip around


def tank(left, right):
    """Left side speed, right side speed. Positive = forward."""
    left = max(-MAX_SPEED, min(MAX_SPEED, left))
    right = max(-MAX_SPEED, min(MAX_SPEED, right))
    board.set_motor_duty([
        [1, right], [2, right],   # right side: FR, BR
        [3, -left], [4, -left],   # left side: FL, BL (flipped)
    ])


def stop():
    tank(0, 0)


# No matter how the script exits (quit, crash, Ctrl+C), motors stop.
atexit.register(stop)


def getch():
    """Read a single keypress from the terminal, no Enter required."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def main():
    global speed
    print("Watney tank drive — tap-to-move")
    print("W/S fwd/back | A/D turn | SPACE stop | +/- speed | Q quit")
    print(f"Speed: {speed} (cap {MAX_SPEED})")

    while True:
        ch = getch().lower()
        turn = int(speed * TURN_SCALE)

        if ch == 'w':
            tank(speed, speed)
            print(f"forward @ {speed}")
        elif ch == 's':
            tank(-speed, -speed)
            print(f"back @ {speed}")
        elif ch == 'a':
            tank(-turn, turn)        # left side back, right side forward
            print(f"turn left @ {turn}")
        elif ch == 'd':
            tank(turn, -turn)        # left side forward, right side back
            print(f"turn right @ {turn}")
        elif ch == ' ':
            stop()
            print("STOP")
        elif ch in ('+', '='):
            speed = min(speed + 10, MAX_SPEED)
            print(f"speed -> {speed}")
        elif ch in ('-', '_'):
            speed = max(speed - 10, 10)
            print(f"speed -> {speed}")
        elif ch == 'q' or ch == '\x03':             # q or Ctrl+C
            stop()
            print("quitting — motors stopped")
            break


if __name__ == '__main__':
    try:
        main()
    finally:
        stop()