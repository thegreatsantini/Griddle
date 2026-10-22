#!/usr/bin/env python3
# servo_tune.py - find the claw and arm pulse numbers for griddle/backends/masterpi.py
# Runs ON Watney.
#
#   1-6   pick a servo           j / k   pulse -25 / +25
#   J / K pulse -100 / +100      c       center (1500)
#   p     print every value      q       quit
#
# Go SLOW near the ends of travel. If a servo buzzes and strains, back it off.

import sys
import termios
import tty

from common.ros_robot_controller_sdk import Board

board = Board()
pulses = {i: None for i in range(1, 7)}   # None = never touched, don't guess
current = 1


def send(sid, pulse):
    pulse = max(500, min(2500, pulse))
    pulses[sid] = pulse
    board.pwm_servo_set_position(0.3, [[sid, pulse]])
    print(f"servo {sid} -> {pulse}")


def getch():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        return sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


print("1-6 servo | j/k +-25 | J/K +-100 | c center | p print | q quit")
while True:
    ch = getch()
    if ch in "123456":
        current = int(ch)
        print(f"servo {current} selected (pulse {pulses[current]})")
    elif ch in "jkJK":
        base = pulses[current] if pulses[current] is not None else 1500
        step = {"j": -25, "k": 25, "J": -100, "K": 100}[ch]
        send(current, base + step)
    elif ch == "c":
        send(current, 1500)
    elif ch == "p":
        touched = {k: v for k, v in pulses.items() if v is not None}
        print(f"pose = {touched}")
    elif ch in ("q", "\x03"):
        touched = {k: v for k, v in pulses.items() if v is not None}
        print(f"final pose = {touched}")
        break
