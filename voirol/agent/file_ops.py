import os
import shlex
import subprocess

from voirol.utils.logger import get_logger
from voirol.command.actions import FILE_SEARCH_DIRS
from voirol.command.maps import APP_MAP

logger = get_logger("agent.file_ops")

_SAFE_WRITE_DIRS = [
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Downloads"),
    os.getcwd(),
]


def _is_safe_path(path: str, allowed_dirs: list[str] | None = None) -> bool:
    try:
        real = os.path.realpath(os.path.expanduser(path))
    except (OSError, ValueError):
        return False
    dirs = allowed_dirs or _SAFE_WRITE_DIRS
    for d in dirs:
        try:
            d_real = os.path.realpath(d)
            if os.path.commonpath([real, d_real]) == d_real:
                return True
        except (OSError, ValueError):
            continue
    return False


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


_ALLOWED_COMMANDS = {"dir", "ls", "echo", "cd", "pwd", "mkdir", "type", "cat"}

_DANGEROUS_PATTERNS = {
    "format", "del", "rmdir", "rd", "erase", "shutdown", "restart",
    "reg delete", "reg add", "diskpart", "format", "mkfs",
    "cmd /c", "powershell -", "bash -c",
}


def _validate_command(command: str) -> tuple[bool, str]:
    """校验命令是否在白名单内且不含危险模式。

    返回 (是否允许, 原因)。允许的命令需满足：
    1. 命令首部（空格前的第一个 token）在 _ALLOWED_COMMANDS 中
    2. 不包含 _DANGEROUS_PATTERNS 中的任何模式
    3. 不包含重定向操作符 > < | & 以防写入/管道执行任意程序
    """
    if not command or not command.strip():
        return False, "空命令"

    stripped = command.strip()

    lower = stripped.lower()
    for pattern in _DANGEROUS_PATTERNS:
        if pattern in lower:
            return False, f"命令包含被禁止的模式: {pattern}"

    for ch in (">", "<", "|", "&"):
        if ch in stripped:
            return False, f"命令包含被禁止的字符: {ch!r}"

    first_token = stripped.split()[0].lower()
    first_token_no_ext = first_token.replace(".exe", "").replace(".com", "")
    if first_token not in _ALLOWED_COMMANDS and first_token_no_ext not in _ALLOWED_COMMANDS:
        return False, f"命令 '{first_token}' 不在白名单中，允许的命令: {sorted(_ALLOWED_COMMANDS)}"

    return True, ""


def skill_run_command(params: dict) -> str:
    command = params["command"]
    cwd = params.get("cwd")
    timeout = params.get("timeout", 30)

    allowed, reason = _validate_command(command)
    if not allowed:
        logger.warning(f"Command rejected: {reason} (command={command!r})")
        return f"Error: 命令被拒绝 - {reason}"

    try:
        if os.name == "nt":
            args = ["cmd", "/q", "/c", command]
        else:
            args = ["/bin/sh", "-c", command]
    except Exception:
        return "Error: malformed command"

    try:
        r = subprocess.run(
            args,
            shell=False,
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
    if not _is_safe_path(path):
        return f"Error: access denied to '{path}'"
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
    if not _is_safe_path(path):
        return f"Error: access denied to '{path}'"
    content = params["content"]
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Wrote {len(content)} bytes to '{path}'")
        return f"Wrote {len(content)} bytes to '{path}'"
    except (OSError, UnicodeEncodeError) as e:
        logger.warning(f"Failed to write file '{path}': {e}")
        return f"Error writing '{path}': {e}"


_FILE_NAVIGATOR_SEARCH_DIRS: list[str] = FILE_SEARCH_DIRS


_shared_llm_engine = None
_shared_file_navigator = None
_shared_search_dirs = None


def set_shared_engine(llm_engine, file_navigator, search_dirs=None):
    global _shared_llm_engine, _shared_file_navigator, _shared_search_dirs
    _shared_llm_engine = llm_engine
    _shared_file_navigator = file_navigator
    _shared_search_dirs = search_dirs or _FILE_NAVIGATOR_SEARCH_DIRS


def skill_find_file(params: dict) -> str:
    query = params["query"]
    nav = _shared_file_navigator
    if nav is None:
        from voirol.command.file_navigator import FileNavigator
        from voirol.ai.openai_engine import OpenAIEngine
        engine = OpenAIEngine(
            api_url="https://api.deepseek.com/v1",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            model="deepseek-chat",
        )
        nav = FileNavigator(engine, max_depth=5)
    search_dirs = _shared_search_dirs or _FILE_NAVIGATOR_SEARCH_DIRS
    result = nav.find_file(query, search_dirs)
    if result:
        nav.clear_context()
        return f"Found file: {result}"
    return f"File not found: {query}"
