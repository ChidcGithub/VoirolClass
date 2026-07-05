import pyautogui

from voirol.utils.logger import get_logger

logger = get_logger("agent.keyboard")

_HOTKEY_DESC = {
    ("win", "d"): "toggle desktop (show/hide all windows)",
    ("win", "m"): "minimize all windows",
    ("win", "e"): "open File Explorer",
    ("win", "r"): "open Run dialog",
    ("win", "l"): "lock computer",
    ("win", "i"): "open Settings",
    ("alt", "tab"): "switch window",
    ("alt", "f4"): "close active window",
    ("ctrl", "a"): "select all",
    ("ctrl", "c"): "copy",
    ("ctrl", "v"): "paste",
    ("ctrl", "x"): "cut",
    ("ctrl", "z"): "undo",
    ("ctrl", "y"): "redo",
    ("ctrl", "s"): "save",
    ("ctrl", "f"): "find",
    ("ctrl", "shift", "esc"): "open Task Manager",
}


def _hotkey_description(keys: tuple[str, ...]) -> str:
    key_str = "+".join(keys)
    desc = _HOTKEY_DESC.get(keys)
    if desc:
        return key_str + f" ({desc})"
    return key_str


def skill_type_text(params: dict) -> str:
    text = params["text"]
    interval = params.get("interval", 0.05)
    try:
        pyautogui.write(text, interval=interval)
    except pyautogui.FailSafeException:
        logger.warning("FailSafe triggered during type_text")
        return "Error: FailSafe triggered"
    logger.info(f"Typed text (len={len(text)})")
    return f"Typed text (len={len(text)}): {text[:50]}"


def skill_press_key(params: dict) -> str:
    key = params["key"]
    try:
        if "+" in key:
            keys = tuple(key.split("+"))
            pyautogui.hotkey(*keys)
            desc = _hotkey_description(keys)
            logger.info(f"Pressed hotkey: {desc}")
            return f"Pressed hotkey: {desc}"
        else:
            pyautogui.press(key)
            logger.info(f"Pressed key: {key}")
            return f"Pressed key: {key}"
    except pyautogui.FailSafeException:
        logger.warning("FailSafe triggered during press_key")
        return "Error: FailSafe triggered"


def skill_hotkey(params: dict) -> str:
    keys = params["keys"]
    if isinstance(keys, str):
        keys = [keys]
    keys = tuple(keys)
    try:
        pyautogui.hotkey(*keys)
    except pyautogui.FailSafeException:
        logger.warning("FailSafe triggered during hotkey")
        return "Error: FailSafe triggered"
    desc = _hotkey_description(keys)
    logger.info(f"Hotkey: {desc}")
    return f"Pressed hotkey: {desc}"


def skill_press_and_release(params: dict) -> str:
    keys = params["keys"]
    if isinstance(keys, str):
        keys = [keys]
    try:
        for k in keys:
            pyautogui.keyDown(k)
        for k in reversed(keys):
            pyautogui.keyUp(k)
    except pyautogui.FailSafeException:
        logger.warning("FailSafe triggered during press_and_release")
        return "Error: FailSafe triggered"
    logger.info(f"Press and release: {'+'.join(keys)}")
    return f"Press and release: {'+'.join(keys)}"
