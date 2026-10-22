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
    cube = bot.find_cube(color)

    if step == "search":
        if cube is None:
            bot.drive(0, SEARCH_TURN)
        else:
            print(f"{bot.time:4.1f}s  spotted it! offset {cube.x_offset:+.2f} size {cube.size:.2f}")
            step = "approach"

    elif step == "approach":
        if cube is None:
            if last_size > GRAB_SIZE * 0.7:
                # Lost it because it's right under the claw - good enough.
                bot.stop()
                bot.grab()
                step = "grabbing"
            else:
                step = "search"
            return
        last_size = cube.size
        turn = cube.x_offset * STEER
        fwd = APPROACH_SPEED if abs(cube.x_offset) < 0.3 else 0.0   # aim first, then drive
        bot.drive(fwd, turn)
        if cube.size >= GRAB_SIZE:
            bot.stop()
            bot.grab()
            step = "grabbing"

    elif step == "grabbing":
        if not bot.busy:
            print(f"{bot.time:4.1f}s  got it (hopefully) - driver, take it home!")
            step = "done"

    else:
        bot.stop()
