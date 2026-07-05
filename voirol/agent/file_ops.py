import os
import subprocess

from voirol.utils.logger import get_logger
from voirol.command.maps import APP_MAP

logger = get_logger("agent.file_ops")


def skill_open_app(params: dict) -> str:
    name = params["name"]
    app = APP_MAP.get(name)
    try:
        if app:
            if app.startswith("ms-"):
                os.startfile(app)
            else:
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
            actual_len = len(content)
            truncated = actual_len > max_chars
            content = content[:max_chars]
            if truncated:
                content += f"\n... (truncated, total {actual_len} bytes)"
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


_FILE_NAVIGATOR_SEARCH_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.getcwd(),
]


def skill_find_file(params: dict) -> str:
    from voirol.command.file_navigator import FileNavigator
    from voirol.ai.openai_engine import OpenAIEngine

    query = params["query"]
    engine = OpenAIEngine(
        api_url="https://api.deepseek.com/v1",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        model="deepseek-chat",
    )
    nav = FileNavigator(engine, max_depth=5)
    search_dirs = _FILE_NAVIGATOR_SEARCH_DIRS
    result = nav.find_file(query, search_dirs)
    if result:
        nav.clear_context()
        return f"Found file: {result}"
    return f"File not found: {query}"
