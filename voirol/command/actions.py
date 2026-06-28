import glob
import os
import re
import subprocess
import time

import pyautogui

from voirol.utils.ai_parse import parse_ai_json_response
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
_selected_file_search_dirs = None
_file_navigator = None
_ai_router_engine = None

APP_MAP = {
    "记事本": "notepad", "notepad": "notepad",
    "计算器": "calc", "calc": "calc",
    "画图": "mspaint", "mspaint": "mspaint",
    "命令提示符": "cmd", "cmd": "cmd", "命令行": "cmd",
    "任务管理器": "taskmgr", "taskmgr": "taskmgr",
    "控制面板": "control", "control": "control",
    "资源管理器": "explorer", "explorer": "explorer",
    "注册表": "regedit", "regedit": "regedit",
    "powershell": "powershell", "PowerShell": "powershell",
    "设置": "ms-settings:", "settings": "ms-settings:",
}

FILE_SEARCH_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.getcwd(),
]


def set_file_search_dirs(dirs: list[str]):
    global _selected_file_search_dirs
    _selected_file_search_dirs = [os.path.expanduser(d) for d in dirs]


def set_file_navigator(nav):
    global _file_navigator
    _file_navigator = nav


def set_ai_router_engine(engine):
    global _ai_router_engine
    _ai_router_engine = engine


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
    stripped = param.strip()
    if stripped and stripped in APP_MAP:
        open_file_action(param)
        return
    if not param:
        param = "about:blank"
    browser, rest = _detect_browser(param)
    url = _resolve_url(rest)
    _open_in_browser(url, browser)


_ROUTER_PROMPT = (
    '你是一个意图分类器。用户说了"打开{{param}}"，判断其意图。\n'
    '只返回一行JSON：\n'
    '- 网址/网页 → {"intent": "url"}\n'
    '- 应用/程序 → {"intent": "app"}\n'
    '- 文件/路径 → {"intent": "file"}\n'
    '- 搜索 → {"intent": "search"}\n'
)


def open_router(param: str = ""):
    if not param:
        logger.warning("Action: open_router -> no param, use '打开 + 内容'")
        return

    param = param.strip()

    if param in APP_MAP:
        open_file_action(param)
        return

    if param in SITE_MAP:
        open_url(param)
        return

    if param.startswith(("http://", "https://", "ftp://", "about:")):
        open_url(param)
        return

    if "." in param and " " not in param.strip("."):
        open_url(param)
        return

    engine = _ai_router_engine
    if engine is not None:
        try:
            prompt = _ROUTER_PROMPT.replace("{{param}}", param)
            messages = [{"role": "user", "content": prompt}]
            response = engine.chat(messages, temperature=0.1, timeout=10)
            if not response:
                logger.warning("AI router returned empty response")
                return
            result = parse_ai_json_response(response)
            if result is None:
                logger.warning("AI router returned unparseable response")
                return
            intent = result.get("intent", "")

            if intent == "url":
                open_url(param)
                return
            elif intent == "search":
                open_url(param)
                return
            elif intent == "app":
                open_file_action(param)
                return
            elif intent == "file":
                open_file_action(param)
                return
            else:
                logger.warning(f"Unknown intent from AI: {intent}")
        except Exception as e:
            logger.warning(f"AI router failed: {e}, giving up")

    logger.warning(f"Action: open_router -> unable to route '{param}'")


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


def open_file_action(param: str = ""):
    if not param:
        logger.warning("Action: open_file -> no param, use '打开 + 文件名'")
        return

    param = param.strip()

    app = APP_MAP.get(param)
    if app:
        try:
            if app.startswith("ms-"):
                subprocess.Popen(["start", app], shell=True)
            else:
                subprocess.Popen(app)
            logger.info(f"Action: open_app -> {app}")
            return
        except Exception as e:
            logger.warning(f"Failed to launch app '{param}': {e}")

    if os.path.isabs(param) and os.path.exists(param):
        try:
            os.startfile(param)
            logger.info(f"Action: open_file -> {param}")
            return
        except Exception as e:
            logger.warning(f"Failed to open path '{param}': {e}")

    dirs = _selected_file_search_dirs or FILE_SEARCH_DIRS
    for search_dir in dirs:
        if not os.path.isdir(search_dir):
            continue
        pattern = os.path.join(search_dir, "**", param)
        matches = glob.glob(pattern, recursive=True)
        if matches:
            try:
                os.startfile(matches[0])
                logger.info(f"Action: open_file -> {matches[0]}")
                return
            except Exception as e:
                logger.warning(f"Failed to open '{matches[0]}': {e}")

    logger.warning(f"Action: open_file -> '{param}' not found")
    nav = _file_navigator
    if nav:
        nav_path = nav.find_file(param, dirs)
        if nav_path:
            try:
                os.startfile(nav_path)
                logger.info(f"Action: open_file (ai) -> {nav_path}")
                nav.clear_context()
                return
            except Exception as e:
                logger.warning(f"Failed to open ai-found '{nav_path}': {e}")
    logger.warning(f"Action: open_file -> '{param}' not found (ai searched)")


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
