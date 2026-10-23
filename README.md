# Griddle

One robot file. Runs in a 2D sim on your laptop and on Watney, no edits.

## Run it

```bash
python3 -m griddle sim starter/starter_auto.py              # laptop, full match
python3 -m griddle sim starter/starter_auto.py --auto-only  # just the 30s auto
python3 -m griddle sim starter/seek_example.py --color blue # pretend blue was drawn
python3 -m griddle sim my_bot.py --speed 3                  # 3x faster
python3 -m griddle run starter/starter_auto.py              # on Watney
python3 -m griddle run my_bot.py --color red                # ref override if the camera can't tell
```

Run from the repo root. Works on Python 3.7+, Mac/Linux/Windows.

## Your robot file

Define any of these. The engine calls them; you never write `while True` or `sleep()`.

| function | when |
|---|---|
| `autonomous_init(bot)` | once, start of auto |
| `autonomous_periodic(bot)` | 20x/second for 30s |
| `teleop_init(bot)` | once, start of teleop |
| `teleop_periodic(bot, key)` | 20x/second for 2 min. Skip it to use the built-in controls |

## The bot

```python
bot.drive(fwd, turn)       # -1..1 each. turn > 0 = right
bot.stop()
bot.grab() / bot.release() # take ~1s; check bot.busy
bot.busy                   # True while the claw is moving
bot.time                   # seconds since this period started
bot.find_cube("red")       # None, or .x_offset (-1 left..1 right) and .size (bigger = closer)
bot.detect_shown_color()   # "red", "green", "blue", or "unknown"
bot.floor_color()          # goal square under the claw: "red", "green", "blue", or None
```

## Built-in driver controls

`W/S` forward/back, `A/D` turn, `SPACE` stop, `G` grab, `R` release, `+/-` speed, `Q` quit.
Keys latch like piground: the robot keeps doing the last thing until you press another key.

## Safety

The motors stop when a period ends, when you press Q or Ctrl+C, and when student code crashes.
A crash in auto stops the robot for the rest of auto. A crash in teleop falls back to the built-in controls.

## Calibrating Watney (`griddle/backends/masterpi.py`)

1. `python3 tools/servo_tune.py`. Find the claw open/closed pulses, set `CLAW_OPEN` / `CLAW_CLOSED`.
2. Optional: tune `ARM_DOWN` / `ARM_UP`, then flip `ARM_CALIBRATED = True`. Until then only the claw moves.
3. Vision: if `find_cube` misses, adjust `HSV_RANGES` under the venue lights.
   `floor_color()` needs the camera tilted to see the floor; tune `FLOOR_ROI_TOP` and `FLOOR_MIN_FRACTION`.
4. Measure real speed (ft/s at full) and turn rate (rad/s at full), and put them in `griddle/backends/sim.py` so the sim matches.

## Field (`griddle/backends/sim.py`)

Goals are the painted squares in the top row: red, green, blue, left to right.
Six cubes sit on a line at y = 36". Pick the color layout with `LAYOUT` (L1, L2, or L3 shuffled).
`BLOCK_X`, `START_POSE`, and `GOAL_INSET` should match tape-measure numbers from the real mat.