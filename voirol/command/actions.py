import re
import subprocess
import time

import pyautogui

from voirol.utils.logger import get_logger

logger = get_logger("command.actions")

SITE_MAP = {
    "百度": "https://www.baidu.com",
    "哔哩哔哩": "https://www.bilibili.com",
    "b站": "https://www.bilibili.com",
    "bilibili": "https://www.bilibili.com",
    "知乎": "https://www.zhihu.com",
    "淘宝": "https://www.taobao.com",
    "京东": "https://www.jd.com",
    "微博": "https://www.weibo.com",
    "微信": "https://weixin.qq.com",
    "抖音": "https://www.douyin.com",
    "csdn": "https://www.csdn.net",
    "github": "https://github.com",
    "谷歌": "https://www.google.com",
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "腾讯": "https://www.tencent.com",
    "阿里巴巴": "https://www.alibaba.com",
    "bing": "https://www.bing.com",
    "必应": "https://www.bing.com",
    "搜狗": "https://www.sogou.com",
    "360": "https://www.so.com",
    "163": "https://www.163.com",
    "网易": "https://www.163.com",
    "新浪": "https://www.sina.com.cn",
    "搜狐": "https://www.sohu.com",
    "qq": "https://www.qq.com",
    "腾讯qq": "https://www.qq.com",
    "百度云": "https://pan.baidu.com",
    "百度网盘": "https://pan.baidu.com",
    "阿里云": "https://www.aliyun.com",
    "腾讯云": "https://cloud.tencent.com",
}

BROWSER_ALIASES = {
    "edge": "edge",
    "微软": "edge",
    "chrome": "chrome",
    "谷歌": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "火狐": "firefox",
    "ie": "ie",
    "ie浏览器": "ie",
}

DEFAULT_SEARCH_ENGINES = {
    "zh": "https://www.baidu.com/s?wd={}",
    "en": "https://www.google.com/search?q={}",
}

_selected_browser = "edge"
_selected_search_engine = None


def set_default_browser(browser: str):
    global _selected_browser
    if browser in BROWSER_ALIASES:
        _selected_browser = BROWSER_ALIASES[browser]
    else:
        _selected_browser = browser


def set_search_engine(url_template: str):
    global _selected_search_engine
    _selected_search_engine = url_template


def _detect_browser(text: str) -> tuple[str, str]:
    text_lower = text.lower()
    m = re.search(
        r'(?:用|使用|通过)\s*(.+?)\s*(?:打开|访问|搜索|前往|进入|启动)',
        text_lower,
    )
    if m:
        raw = m.group(1).strip()
        for alias, canonical in BROWSER_ALIASES.items():
            if raw == alias or raw.startswith(alias):
                remaining = text[m.end():].strip()
                return canonical, remaining
    return _selected_browser, text


def _resolve_url(text: str) -> str:
    text = text.strip()
    if not text:
        return "about:blank"

    lower = text.lower()

    if text in SITE_MAP:
        return SITE_MAP[text]

    for name, url in sorted(SITE_MAP.items(), key=lambda x: -len(x[0])):
        if name.lower() in lower:
            return url

    if text.startswith(("about:", "http://", "https://", "ftp://")):
        return text

    if "." in text and " " not in text.strip("."):
        return "https://" + text

    engine_url = _selected_search_engine or DEFAULT_SEARCH_ENGINES.get("zh")
    engine_url = engine_url.replace("%s", "{}")
    import urllib.parse
    return engine_url.format(urllib.parse.quote(text))


def _open_in_browser(url: str, browser: str):
    import webbrowser
    try:
        if browser == "edge":
            webbrowser.open(f"microsoft-edge:{url}")
        elif browser == "chrome":
            try:
                chrome = webbrowser.get("chrome")
                chrome.open(url)
            except Exception:
                webbrowser.open(url)
        elif browser == "firefox":
            try:
                ff = webbrowser.get("firefox")
                ff.open(url)
            except Exception:
                webbrowser.open(url)
        else:
            webbrowser.open(url)

        logger.info(f"Action: open_url -> {url} in {browser}")
    except Exception as e:
        logger.error(f"Failed to open browser ({browser}): {e}")
        try:
            webbrowser.open(url)
        except Exception:
            pass


def open_url(param: str = ""):
    if not param:
        param = "about:blank"
    browser, rest = _detect_browser(param)
    url = _resolve_url(rest)
    _open_in_browser(url, browser)


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
