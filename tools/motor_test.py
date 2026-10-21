import time
from common.ros_robot_controller_sdk import Board

board = Board()
for m in (1, 2, 3, 4):
    print(f"motor {m}")
    board.set_motor_duty([[m, 40]])
    time.sleep(1.5)
    board.set_motor_duty([[m, 0]])
    time.sleep(1)