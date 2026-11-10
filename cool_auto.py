"""LEVEL UP - use the camera to hunt down the cube of YOUR drawn color.

1. Spin until the camera sees our color
2. Steer toward it (x_offset says how far left/right it is)
3. Drive in until it looks big (size says how close it is)
4. Grab it - then the driver brings it home in teleop
"""

SEARCH_TURN = 0.35      # how fast to spin while looking
STEER = 0.6             # bigger = steers harder toward the cube
APPROACH_SPEED = 0.35
GRAB_SIZE = 0.4         # cube this big in the frame = close enough to grab (TUNE on Watney)

color = "red"
step = "search"
last_size = 0.0


def autonomous_init(bot):
    global color
    seen = bot.detect_shown_color()
    if seen in ("red", "green", "blue"):
        color = seen
    print(f"hunting for {color}")


def autonomous_periodic(bot):
    global step, last_size
    if step == "search":
        bot.drive(1, 0.1)  # default to stopped
        bot.drive(1, 0)  # default to stopped
        bot.drive(1, -0.1)
        bot.drive(3, 0)
        bot.stop()
        step = "done"
    if step == "done":
        return