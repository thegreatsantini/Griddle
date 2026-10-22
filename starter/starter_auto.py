"""STARTER AUTO - scores the freebie cube with zero edits.

Drive straight to the freebie, grab it, keep driving into the pen, drop it.

Run it:
    python -m griddle sim starter/starter_auto.py      (laptop)
    python -m griddle run starter/starter_auto.py      (Watney)

How it works: autonomous_periodic() runs 20 times every second. It is NOT
a list of steps that runs once - so we remember which `step` we're on, and
check bot.time to know how long we've been on it.
"""

# ---- Tune these on the real mat ----
DRIVE_SPEED = 0.5
TO_CUBE_SECONDS = 2.2       # start -> freebie
TO_PEN_SECONDS = 4.0        # freebie -> inside the pen
BACK_UP_SECONDS = 1.0       # back off so we don't drag the cube out

step = "start"
step_started = 0.0


def go(new_step, bot):
    """Switch to a new step and start its timer."""
    global step, step_started
    step = new_step
    step_started = bot.time
    print(f"{bot.time:4.1f}s  -> {new_step}")


def autonomous_init(bot):
    color = bot.detect_shown_color()
    print(f"we were shown: {color}")
    go("to_cube", bot)


def autonomous_periodic(bot):
    t = bot.time - step_started          # seconds spent on this step

    if step == "to_cube":
        bot.drive(DRIVE_SPEED, 0)
        if t >= TO_CUBE_SECONDS:
            bot.stop()
            bot.grab()
            go("grabbing", bot)

    elif step == "grabbing":
        if not bot.busy:                 # claw finished closing
            go("to_pen", bot)

    elif step == "to_pen":
        bot.drive(DRIVE_SPEED, 0)
        if t >= TO_PEN_SECONDS:
            bot.stop()
            bot.release()
            go("releasing", bot)

    elif step == "releasing":
        if not bot.busy:
            go("back_up", bot)

    elif step == "back_up":
        bot.drive(-DRIVE_SPEED, 0)
        if t >= BACK_UP_SECONDS:
            go("done", bot)

    else:  # done
        bot.stop()
