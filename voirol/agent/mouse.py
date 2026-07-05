import pyautogui

from voirol.utils.logger import get_logger

logger = get_logger("agent.mouse")


def _catch_failsafe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except pyautogui.FailSafeException:
        logger.warning("FailSafe triggered during mouse operation")
        raise


def skill_click(params: dict) -> str:
    x = params["x"]
    y = params["y"]
    button = params.get("button", "left")
    try:
        _catch_failsafe(pyautogui.click, x, y, button=button)
    except pyautogui.FailSafeException:
        return "Error: FailSafe triggered"
    logger.info(f"Mouse click at ({x}, {y}) with {button} button")
    return f"Clicked at ({x}, {y}) with {button} button"


def skill_double_click(params: dict) -> str:
    x = params["x"]
    y = params["y"]
    try:
        _catch_failsafe(pyautogui.doubleClick, x, y)
    except pyautogui.FailSafeException:
        return "Error: FailSafe triggered"
    logger.info(f"Mouse double-click at ({x}, {y})")
    return f"Double-clicked at ({x}, {y})"


def skill_right_click(params: dict) -> str:
    x = params["x"]
    y = params["y"]
    try:
        _catch_failsafe(pyautogui.rightClick, x, y)
    except pyautogui.FailSafeException:
        return "Error: FailSafe triggered"
    logger.info(f"Mouse right-click at ({x}, {y})")
    return f"Right-clicked at ({x}, {y})"


def skill_drag(params: dict) -> str:
    from_x = params["from_x"]
    from_y = params["from_y"]
    to_x = params["to_x"]
    to_y = params["to_y"]
    duration = params.get("duration", 0.5)
    try:
        _catch_failsafe(pyautogui.moveTo, from_x, from_y)
        _catch_failsafe(pyautogui.drag, to_x - from_x, to_y - from_y, duration=duration)
    except pyautogui.FailSafeException:
        return "Error: FailSafe triggered"
    logger.info(f"Mouse drag from ({from_x}, {from_y}) to ({to_x}, {to_y})")
    return f"Dragged from ({from_x}, {from_y}) to ({to_x}, {to_y})"


def skill_scroll(params: dict) -> str:
    clicks = params["clicks"]
    x = params.get("x")
    y = params.get("y")
    try:
        if x is not None and y is not None:
            _catch_failsafe(pyautogui.moveTo, x, y)
        pyautogui.scroll(clicks)
    except pyautogui.FailSafeException:
        return "Error: FailSafe triggered"
    logger.info(f"Mouse scroll {clicks} clicks")
    return f"Scrolled {clicks} clicks"


def skill_move_mouse(params: dict) -> str:
    x = params["x"]
    y = params["y"]
    duration = params.get("duration", 0.3)
    try:
        _catch_failsafe(pyautogui.moveTo, x, y, duration=duration)
    except pyautogui.FailSafeException:
        return "Error: FailSafe triggered"
    logger.info(f"Mouse moved to ({x}, {y})")
    return f"Moved mouse to ({x}, {y})"
