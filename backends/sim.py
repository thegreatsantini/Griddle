import math

from griddle.backends.base import Backend, Cube

FIELD_SIZE = 6.0        # feet, square
MAX_SPEED = 1.5         # feet per second at fwd = 1.0
MAX_TURN_RATE = 3.14    # radians per second at turn = 1.0
GRAB_TIME = 1.0         # seconds for a grab or release to finish