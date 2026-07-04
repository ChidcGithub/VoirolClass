import os
import subprocess

from voirol.utils.logger import get_logger

logger = get_logger("agent.file_ops")

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


def skill_open_app(params: dict) -> str:
    name = params["name"]
    app = APP_MAP.get(name)
    try:
        if app:
            subprocess.Popen(app)
        else:
            os.startfile(name)
    except Exception as e:
        logger.warning(f"Failed to open '{name}': {e}")
        return f"Error opening '{name}': {e}"
    logger.info(f"Opened app: {name}")
    return f"Opened: {name}"


def skill_run_command(params: dict) -> str:
    command = params["command"]
    cwd = params.get("cwd")
    timeout = params.get("timeout", 30)
    try:
        r = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        logger.info(f"Command executed (rc={r.returncode}): {command[:60]}")
        out = (r.stdout[:300] + "...") if len(r.stdout) > 300 else r.stdout
        err = (r.stderr[:200] + "...") if len(r.stderr) > 200 else r.stderr
        return f"cmd rc={r.returncode} | stdout: {out}" + (f" | stderr: {err}" if err else "")
    except subprocess.TimeoutExpired:
        logger.warning(f"Command timed out after {timeout}s: {command[:60]}")
        return f"Error: command timed out ({timeout}s)"


def skill_read_file(params: dict) -> str:
    path = params["path"]
    max_chars = params.get("max_chars", 5000)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read(max_chars + 1)
            truncated = len(content) > max_chars
            content = content[:max_chars]
            if truncated:
                content += f"\n... (truncated, total N bytes)"
        return f"File {path}: {content}"
    except (FileNotFoundError, UnicodeDecodeError, OSError) as e:
        logger.warning(f"Failed to read file '{path}': {e}")
        return f"Error reading '{path}': {e}"


def skill_write_file(params: dict) -> str:
    path = params["path"]
    content = params["content"]
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Wrote {len(content)} bytes to '{path}'")
        return f"Wrote {len(content)} bytes to '{path}'"
    except (OSError, UnicodeEncodeError) as e:
        logger.warning(f"Failed to write file '{path}': {e}")
        return f"Error writing '{path}': {e}"
