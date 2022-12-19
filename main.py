import cv2

from utils.grabbers.mss import Grabber
from utils.fps import FPS
import multiprocessing

from utils.controls.mouse.win32 import MouseControls
from utils.win32 import WinHelper
import keyboard

import time
from utils.time import sleep

# config
ACTIVATION_HOTKEY = 58  # 58 = CAPS-LOCK
sniper_mode = False
fov = (10, 10)  # capture fov box
diff_threshold = 2000
red_level_treshold = 40000
_show_cv2 = True
_clear_decals = True
_use_playerid_detection = False
_shots_interval = 0.2  # 0.2 is good for Ak-47 or M4A1-S, 0.4 is good for UPS/Glock

# used by the script
game_window_rect = WinHelper.GetWindowRect("Counter-Strike: Global Offensive - Direct3D 9",
                                           (8, 30, 16, 39))  # cut the borders
_active = False
_focus_sum = None
_last_shot = 0

# Force 0 shot interval for sniper mode
if sniper_mode:
    _shots_interval = 0

# Force using playerid for auto shooting
if not sniper_mode and not _use_playerid_detection:
    print("Forcing playerid detection, because sniper mode is not active ...")
    _use_playerid_detection = True
    red_level_treshold /= 2


def grab_process(q):
    global _use_playerid_detection
    grabber = Grabber()

    while True:
        if sniper_mode:
            crosshair_img = grabber.get_image({
                "left": int(game_window_rect[0] + (game_window_rect[2] / 2) - fov[0] / 2),
                "top": int(game_window_rect[1] + (game_window_rect[3] / 2) - fov[1] / 2),
                "width": int(fov[0]),
                "height": int(fov[1])})
        else:
            crosshair_img = None

        if _use_playerid_detection:
            playerid_img = grabber.get_image({
                "left": int(game_window_rect[0] + (game_window_rect[2] / 2) - fov[0] / 2) - 13,
                "top": int(game_window_rect[1] + (game_window_rect[3] / 2) - fov[1] / 2) + 51,
                "width": 42,
                "height": 14})
        else:
            playerid_img = None

        q.put_nowait((crosshair_img, playerid_img))
        q.join()


def cv2_process(q):
    global _show_cv2, _active, _focus_sum, diff_threshold, red_level_treshold, _use_playerid_detection, sniper_mode, _shots_interval, _last_shot

    fps = FPS()
    font = cv2.FONT_HERSHEY_SIMPLEX

    mouse = MouseControls()

    while True:
        if not q.empty():
            crosshair_img, playerid_img = q.get_nowait()
            q.task_done()

            # some processing code
            # OpenCV HSV Scale (H: 0-179, S: 0-255, V: 0-255)
            # hue_point = 87
            # _color = ((hue_point, 100, 100), (hue_point + 20, 255, 255))  # HSV
            # hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

            if _active:
                if sniper_mode:
                    current_sum = crosshair_img.sum()
                is_targeting_enemy = True
                _shoot = False

                if _use_playerid_detection:
                    _red_point = ((0, 75, 75), (10, 255, 255))
                    _red_point2 = ((170, 50, 50), (180, 255, 255))
                    playerid_hsv = cv2.cvtColor(playerid_img, cv2.COLOR_BGR2HSV)

                    red_mask = cv2.inRange(playerid_hsv, _red_point[0], _red_point[1])
                    red_mask2 = cv2.inRange(playerid_hsv, _red_point2[0], _red_point2[1])

                    # red_mask__not = cv2.bitwise_not(red_mask)
                    red_mask = cv2.bitwise_or(red_mask, red_mask2)
                    red_mask = cv2.bitwise_and(playerid_hsv, playerid_hsv, mask=red_mask)
                    playerid_img = cv2.cvtColor(red_mask, cv2.COLOR_HSV2BGR)

                    # avg_color_per_row = np.average(red_mask, axis=0)
                    # avg_color = np.average(avg_color_per_row, axis=0)
                    # is_targeting_enemy = 7 < avg_color[0] < 22 and ((avg_color[1] > 185 or avg_color[2] > 185) or (avg_color[1] > 100 and avg_color[2] > 100))

                    print("RED LEVEL", red_mask.sum())
                    is_targeting_enemy = red_mask.sum() > red_level_treshold

                    if is_targeting_enemy:
                        print("[ENEMY] playerid detection")
                    else:
                        print("[etc] playerid detection")

                if sniper_mode:
                    print("CURRENT", current_sum, "FOCUS", _focus_sum, "DIFF",
                          abs(max((_focus_sum, current_sum)) - min(_focus_sum, current_sum)))
                print("===")

                if sniper_mode:
                    _shoot = (_focus_sum > (current_sum + diff_threshold)
                              or _focus_sum < (current_sum - diff_threshold)) \
                             and is_targeting_enemy
                else:
                    _shoot = is_targeting_enemy

                    if bool(_shots_interval) and time.perf_counter() < (_last_shot + _shots_interval):
                        _shoot = False

                if _shoot:
                    mouse.hold_mouse()
                    sleep(0.02)
                    mouse.release_mouse()

                    _last_shot = time.perf_counter()  # save last shot time

                    # only clear decals in sniper mode (bind r_cleardecals in game for non-sniper mode)
                    if sniper_mode and _clear_decals:
                        keyboard.press_and_release("~")  # open console
                        sleep(0.02)
                        keyboard.write("r_cleardecals")  # write command
                        keyboard.press_and_release("enter")  # enter the command
                        keyboard.press_and_release("~")  # close console

                    if sniper_mode:
                        _active = False  # shot only once in sniper mode
            elif sniper_mode:
                _focus_sum = crosshair_img.sum()

            # cv stuff
            # img = mask
            if _show_cv2:
                if _use_playerid_detection:
                    playerid_img = cv2.putText(playerid_img, f"{fps():.2f}", (3, 10), font,
                                               .3, (0, 255, 0), 1, cv2.LINE_AA)
                # cv2.imshow("test", cv2.cvtColor(img, cv2.COLOR_RGB2BGRA))
                # mask = cv2.resize(mask, (1280, 720))

                if sniper_mode:
                    crosshair_img = cv2.resize(crosshair_img, (100, 100))

                if _use_playerid_detection:
                    playerid_img = cv2.resize(playerid_img, (playerid_img.shape[1] * 4, playerid_img.shape[0] * 4))
                # red_mask = cv2.resize(red_mask, (playerid_img.shape[1] * 4, playerid_img.shape[0] * 4))

                if sniper_mode:
                    cv2.imshow("Crosshair", crosshair_img)

                if _use_playerid_detection:
                    cv2.imshow("Playerid", playerid_img)
                cv2.waitKey(1)


def switch_shoot_state(triggered, hotkey):
    global _active
    _active = not _active  # inverse value

    if _active:
        print("Activated!")
    else:
        print("Deactivated!")


keyboard.add_hotkey(ACTIVATION_HOTKEY, switch_shoot_state, args=('triggered', 'hotkey'))

if __name__ == "__main__":
    q = multiprocessing.JoinableQueue()

    p1 = multiprocessing.Process(target=grab_process, args=(q,))
    p2 = multiprocessing.Process(target=cv2_process, args=(q,))

    p1.start()
    p2.start()
