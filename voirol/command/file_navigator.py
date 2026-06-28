import json
import os
import re
from collections import deque
from typing import Callable

from voirol.ai.openai_engine import OpenAIEngine
from voirol.utils.logger import get_logger

logger = get_logger("command.file_navigator")

DRIVE_PATTERN = re.compile(r"^([a-zA-Z])[盘pP]", re.ASCII)


class FileNavigator:
    def __init__(
        self,
        engine: OpenAIEngine,
        max_depth: int = 5,
        path_callback: Callable[[str], None] | None = None,
    ):
        self._engine = engine
        self._max_depth = max(3, min(10, max_depth))
        self._path_callback = path_callback
        self._history: list[str] = []

    def find_file(self, query: str, search_dirs: list[str] | None = None) -> str | None:
        if not query:
            return None

        self._history.clear()
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
        if os.path.isabs(text):
            return None, text

        path_parts: list[str] = []
        tokens = text.split()
        filename = text

        drive = ""
        if tokens:
            m = DRIVE_PATTERN.match(tokens[0])
            if m:
                drive = f"{m.group(1).upper()}:\\"
                tokens = tokens[1:]

        if drive and tokens:
            *dirs, filename = tokens if len(tokens) > 1 else ([], tokens[0])
            path_parts = [drive] + dirs
            search_root = os.path.join(*path_parts) if path_parts else drive
        elif drive:
            search_root = drive
            filename = ""
        elif len(tokens) >= 2:
            *dirs, filename = tokens
            search_root = os.path.join(*dirs) if dirs else None
        else:
            search_root = None

        if search_root and not os.path.isabs(search_root):
            search_root = os.path.abspath(search_root)

        return search_root, filename

    def _bfs(self, start_dir: str, filename: str) -> str | None:
        queue = deque([(start_dir, 0)])
        visited: set[str] = set()

        while queue:
            current_dir, depth = queue.popleft()

            if current_dir in visited:
                continue
            visited.add(current_dir)

            if self._path_callback:
                self._path_callback(current_dir)

            if depth >= self._max_depth:
                continue

            entries = self._list_dir(current_dir)
            if entries is None:
                continue

            direct_match = self._find_direct_match(entries, filename, current_dir)
            if direct_match:
                return direct_match

            decision = self._ask_ai(current_dir, entries, filename)
            if decision is None:
                continue

            action = decision.get("action")
            target = decision.get("target", "")

            if action == "open_file":
                full_path = os.path.join(current_dir, target) if not os.path.isabs(target) else target
                if os.path.isfile(full_path):
                    return full_path
                logger.warning(f"AI wanted to open '{target}' but file not found")
                continue

            elif action == "enter_dir":
                subdir = os.path.join(current_dir, target) if not os.path.isabs(target) else target
                if os.path.isdir(subdir):
                    self._history.append(f"Entered {subdir}")
                    queue.appendleft((subdir, depth + 1))
                else:
                    logger.warning(f"AI wanted to enter '{target}' but dir not found")
                    if depth < self._max_depth:
                        for entry in entries:
                            entry_path = os.path.join(current_dir, entry.name)
                            if os.path.isdir(entry_path) and entry_path not in visited:
                                queue.append((entry_path, depth + 1))

            elif action == "up":
                parent = os.path.dirname(current_dir)
                if parent and parent != current_dir and os.path.isdir(parent):
                    self._history.append(f"Went up from {current_dir}")
                    queue.append((parent, depth - 1) if depth > 0 else (parent, 0))

            elif action == "retry":
                self._history.append(f"Retry with '{target}'")
                for entry in entries:
                    entry_path = os.path.join(current_dir, entry.name)
                    if os.path.isdir(entry_path) and entry_path not in visited:
                        match = self._find_direct_match(entries, target, current_dir)
                        if match:
                            return match
                        queue.append((entry_path, depth + 1))

            elif action == "giveup":
                logger.info(f"AI gave up searching for '{filename}' in {current_dir}")
                return None

        return None

    def _list_dir(self, path: str):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
            return entries
        except PermissionError:
            return None
        except OSError as e:
            logger.debug(f"Cannot list {path}: {e}")
            return None

    def _find_direct_match(self, entries, filename: str, current_dir: str) -> str | None:
        lower_filename = filename.lower().strip()
        if not lower_filename:
            return None
        for entry in entries:
            if entry.is_file():
                entry_lower = entry.name.lower()
                if entry_lower == lower_filename or lower_filename in entry_lower:
                    return entry.path
        return None

    def _build_prompt(self, path: str, entries, filename: str) -> str:
        lines = [f"当前目录: {path}", "", "内容:"]
        for e in entries:
            prefix = "📁 " if e.is_dir() else "📄 "
            lines.append(f"  {prefix}{e.name}")

        lines.extend([
            "",
            f"用户想找: \"{filename}\"",
        ])

        if self._history:
            lines.append(f"操作历史: {', '.join(self._history[-6:])}")

        lines.extend([
            "",
            "请选择下一步，只返回 JSON：",
            '{"action": "open_file", "target": "文件名"}',
            '{"action": "enter_dir", "target": "目录名"}',
            '{"action": "up"}',
            '{"action": "retry", "target": "新关键词"}',
            '{"action": "giveup"}',
        ])

        return "\n".join(lines)

    def _ask_ai(self, path: str, entries, filename: str) -> dict | None:
        prompt = self._build_prompt(path, entries, filename)
        try:
            response = self._engine.chat(prompt)
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            cleaned = cleaned.strip("`").strip()

            result = json.loads(cleaned)
            if not isinstance(result, dict) or "action" not in result:
                logger.warning(f"AI returned unexpected format: {result}")
                return None
            return result
        except json.JSONDecodeError:
            logger.warning(f"AI returned invalid JSON: {response}")
            return None
        except Exception as e:
            logger.error(f"AI call failed: {e}")
            return None
