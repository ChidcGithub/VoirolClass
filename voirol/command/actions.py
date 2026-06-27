import subprocess
import time

import pyautogui

from voirol.utils.logger import get_logger

logger = get_logger("command.actions")


def next_page():
    pyautogui.press("right")
    logger.info("Action: next_page")


def prev_page():
    pyautogui.press("left")
    logger.info("Action: prev_page")


def black_screen():
    pyautogui.hotkey("win", "ctrl", "shift", "b")
    logger.info("Action: black_screen")

    try:
        import ctypes
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x0112, 0xF170, 2)
    except Exception:
        pass


def white_screen():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.attributes("-fullscreen", True)
        root.attributes("-topmost", True)
        root.configure(bg="white")
        root.bind("<Escape>", lambda e: root.destroy())
        root.mainloop()
    except Exception as e:
        logger.error(f"white_screen failed: {e}")


def open_whiteboard():
    try:
        subprocess.Popen("mspaint")
        logger.info("Action: open_whiteboard")
    except Exception as e:
        logger.error(f"Failed to open whiteboard: {e}")


def open_browser():
    try:
        import webbrowser
        webbrowser.open("about:blank")
        logger.info("Action: open_browser")
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")


def open_file_dialog():
    pyautogui.hotkey("ctrl", "o")
    logger.info("Action: open_file_dialog")


def volume_up(step: int = 5):
    for _ in range(step):
        pyautogui.press("volumeup")
    logger.info(f"Action: volume_up (step={step})")


def volume_down(step: int = 5):
    for _ in range(step):
        pyautogui.press("volumedown")
    logger.info(f"Action: volume_down (step={step})")


def mute():
    pyautogui.press("volumemute")
    logger.info("Action: mute")


def fullscreen():
    pyautogui.press("f11")
    logger.info("Action: fullscreen")


def esc():
    pyautogui.press("esc")
    logger.info("Action: esc")


def enter():
    pyautogui.press("enter")
    logger.info("Action: enter")


def space():
    pyautogui.press("space")
    logger.info("Action: space")
