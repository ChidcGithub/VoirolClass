import os
import re
from collections import deque
from typing import Callable

from voirol.ai.openai_engine import OpenAIEngine
from voirol.utils.ai_parse import parse_ai_json_response
from voirol.utils.logger import get_logger

logger = get_logger("command.file_navigator")

DRIVE_PATTERN = re.compile(r"^([a-zA-Z])[盘pP]", re.ASCII)

_SYSTEM_PROMPT = (
    "你是文件导航助手。你的任务是帮用户在 Windows 电脑上找到文件或浏览目录。\n"
    "根据当前目录的内容，选择最合适的下一步操作，只返回 JSON。"
)

_MAX_CONTEXT_ROUNDS = 3
_MAX_VISIBLE_ENTRIES = 50
_MAX_SUBDIR_ENTRIES = 5


class FileNavigator:
    def __init__(
        self,
        engine: OpenAIEngine,
        max_depth: int = 5,
        status_callback: Callable[[str], None] | None = None,
    ):
        self._engine = engine
        self._max_depth = max(3, min(10, max_depth))
        self._status_callback = status_callback
        self._context: list[dict] = []
        self._dir_cache: dict[str, list | None] = {}

    def clear_context(self):
        self._context.clear()
        self._dir_cache.clear()

    def find_file(self, query: str, search_dirs: list[str] | None = None) -> str | None:
        if not query:
            return None

        self._dir_cache.clear()

        search_root, filename = self._parse_voice_path(query)

        if search_root:
            if os.path.isdir(search_root):
                result = self._bfs(search_root, filename)
                if result:
                    return result
            return None

        dirs = search_dirs or []
        for base in [d for d in dirs if os.path.isdir(d)]:
            result = self._bfs(base, query)
            if result:
                return result

        return None

    def _parse_voice_path(self, text: str) -> tuple[str | None, str]:
        text = text.strip()
        if not text:
            return None, ""

        if os.path.isabs(text):
            return None, text

        m = DRIVE_PATTERN.match(text)
        if not m:
            tokens = text.split()
            if len(tokens) >= 2:
                *dirs, filename = tokens
                search_root = os.path.join(*dirs)
                if not os.path.isabs(search_root):
                    search_root = os.path.abspath(search_root)
                return search_root, filename
            return None, text

        drive = f"{m.group(1).upper()}:\\"
        rest = text[m.end():].strip()

        if not rest:
            return drive, ""

        parts = rest.replace("/", "\\").split("\\")
        all_parts = [p for t in parts for p in t.split() if p]

        if len(all_parts) >= 2:
            *dirs, filename = all_parts
            return os.path.join(drive, *dirs), filename

        return drive, all_parts[0]

    def _bfs(self, start_dir: str, filename: str) -> str | None:
        queue = deque([(start_dir, 0)])
        visited: set[str] = set()

        while queue:
            current_dir, depth = queue.popleft()

            if current_dir in visited:
                continue
            visited.add(current_dir)

            if self._status_callback:
                self._status_callback(f"🔍 {current_dir}")

            if depth >= self._max_depth:
                continue

            entries = self._list_dir(current_dir)
            if entries is None:
                continue

            decision = self._ask_ai(current_dir, entries, filename)
            if decision is None:
                if self._status_callback:
                    self._status_callback("🤔 解析失败，继续搜索...")
                continue

            action = decision.get("action")
            target = decision.get("target", "")

            if action == "open_file":
                full_path = os.path.join(current_dir, target) if not os.path.isabs(target) else target
                if os.path.isfile(full_path):
                    if self._status_callback:
                        self._status_callback(f"✅ {target}")
                    return full_path
                if self._status_callback:
                    self._status_callback(f"⚠️ {target} 未找到")
                logger.warning(f"AI wanted to open '{target}' but file not found")
                continue

            elif action == "enter_dir":
                subdir = os.path.join(current_dir, target) if not os.path.isabs(target) else target
                if os.path.isdir(subdir):
                    if self._status_callback:
                        self._status_callback(f"📁 进入 {target}")
                    queue.appendleft((subdir, depth + 1))
                else:
                    if self._status_callback:
                        self._status_callback(f"⚠️ 目录 {target} 不存在")
                    logger.warning(f"AI wanted to enter '{target}' but dir not found")
                    for entry in entries:
                        if entry.is_dir():
                            ep = os.path.join(current_dir, entry.name)
                            if ep not in visited:
                                queue.append((ep, depth + 1))

            elif action == "up":
                parent = os.path.dirname(current_dir)
                if parent and parent != current_dir and os.path.isdir(parent):
                    if self._status_callback:
                        self._status_callback("↩️ 返回上层")
                    queue.append((parent, max(0, depth - 1)))

            elif action == "retry":
                if self._status_callback:
                    self._status_callback(f"🔁 重试: {target}")
                filename = target or filename
                for entry in entries:
                    if entry.is_dir():
                        ep = os.path.join(current_dir, entry.name)
                        if ep not in visited:
                            queue.append((ep, depth + 1))

            elif action == "giveup":
                if self._status_callback:
                    self._status_callback("❌ 放弃搜索")
                logger.info(f"AI gave up searching for '{filename}' in {current_dir}")
                return None

        return None

    def _list_dir(self, path: str):
        cached = self._dir_cache.get(path)
        if cached is not None:
            return cached

        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
            self._dir_cache[path] = entries
            return entries
        except PermissionError:
            self._dir_cache[path] = None
            return None
        except OSError as e:
            logger.debug(f"Cannot list {path}: {e}")
            self._dir_cache[path] = None
            return None

    def _build_prompt(self, path: str, entries, filename: str) -> str:
        lines = [f"当前目录: {path}", "", "完整内容:"]
        shown = 0
        for e in entries:
            if shown >= _MAX_VISIBLE_ENTRIES:
                remaining = len(entries) - shown
                lines.append(f"  ... 还有 {remaining} 项")
                break
            shown += 1
            prefix = "📁 " if e.is_dir() else "📄 "
            lines.append(f"  {prefix}{e.name}")
            if e.is_dir():
                sub = self._list_dir(e.path)
                if sub is not None:
                    for s in sub[:_MAX_SUBDIR_ENTRIES]:
                        sp = "📁 " if s.is_dir() else "📄 "
                        lines.append(f"    {sp}{s.name}")
                    if len(sub) > _MAX_SUBDIR_ENTRIES:
                        lines.append(f"    ... 还有 {len(sub) - _MAX_SUBDIR_ENTRIES} 项")

        label = "用户想浏览此目录，请选择操作" if not filename else f"用户想找: \"{filename}\""
        lines.extend([
            "",
            label,
            "",
            "请选择下一步，只返回 JSON：",
            '{"action": "open_file", "target": "文件名"}',
            '{"action": "enter_dir", "target": "目录名"}',
            '{"action": "up"}',
            '{"action": "retry", "target": "新关键词"}',
            '{"action": "giveup"}',
        ])

        return "\n".join(lines)

    def _trim_context(self):
        has_system = self._context and self._context[0].get("role") == "system"
        turns = self._context[1:] if has_system else self._context
        pairs = [turns[i:i+2] for i in range(0, len(turns), 2)]
        if len(pairs) > _MAX_CONTEXT_ROUNDS:
            pairs = pairs[-_MAX_CONTEXT_ROUNDS:]
        flat = [msg for pair in pairs for msg in pair]
        self._context = ([self._context[0]] if has_system else []) + flat

    def _ask_ai(self, path: str, entries, filename: str) -> dict | None:
        if not self._context or self._context[0].get("role") != "system":
            self._context.insert(0, {"role": "system", "content": _SYSTEM_PROMPT})

        prompt = self._build_prompt(path, entries, filename)
        try:
            messages = list(self._context)
            messages.append({"role": "user", "content": prompt})
            response = self._engine.chat(messages, temperature=0.1, timeout=10)
            if not response:
                logger.warning("AI returned empty response")
                return None

            result = parse_ai_json_response(response)
            if result is None or "action" not in result:
                return None

            self._context.append({"role": "user", "content": prompt})
            self._context.append({"role": "assistant", "content": response})
            self._trim_context()
            return result
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None
