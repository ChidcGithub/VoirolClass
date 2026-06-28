from difflib import SequenceMatcher

from voirol.command.registry import Command, CommandRegistry
from voirol.utils.logger import get_logger

logger = get_logger("command.matcher")


class CommandMatcher:
    def __init__(self, registry: CommandRegistry, mode: str = "fuzzy", threshold: float = 0.8):
        self.registry = registry
        self.mode = mode
        self.threshold = threshold

    def match(self, text: str) -> Command | None:
        if not text:
            return None

        text = text.strip().lower()

        if self.mode == "exact":
            return self._exact_match(text)

        cmd = self._keyword_match(text)
        if cmd:
            return cmd

        return self._fuzzy_match(text)

    def match_with_param(self, text: str) -> tuple[Command | None, str | None]:
        cmd = self.match(text)
        if cmd is None or not cmd.capture_param:
            return cmd, None
        kw = self._find_matched_keyword(cmd, text.strip().lower())
        if kw is None:
            return cmd, None
        idx = text.lower().index(kw)
        param = text[idx + len(kw):].strip()
        return cmd, param or None

    def _find_matched_keyword(self, cmd: Command, text: str) -> str | None:
        best_kw = None
        best_len = 0
        for kw in cmd.keywords:
            if kw.lower() in text and len(kw) > best_len:
                best_len = len(kw)
                best_kw = kw
        return best_kw

    def _exact_match(self, text: str) -> Command | None:
        for cmd in self.registry.get_all():
            for keyword in cmd.keywords:
                if text == keyword.lower():
                    logger.info(f"Exact match: '{text}' -> {cmd.id}")
                    return cmd
        return None

    def _keyword_match(self, text: str) -> Command | None:
        best = None
        best_len = 0
        for cmd in self.registry.get_all():
            for kw in cmd.keywords:
                if kw.lower() in text and len(kw) > best_len:
                    best_len = len(kw)
                    best = cmd
        if best:
            logger.info(
                f"Keyword match: '{text}' -> {best.id}"
            )
        return best

    def _fuzzy_match(self, text: str) -> Command | None:
        best_match = None
        best_score = 0.0

        for cmd in self.registry.get_all():
            for keyword in cmd.keywords:
                score = SequenceMatcher(
                    None, text, keyword.lower()
                ).ratio()
                if score > best_score:
                    best_score = score
                    best_match = cmd

        if best_match and best_score >= self.threshold:
            logger.info(
                f"Fuzzy match: '{text}' -> {best_match.id} "
                f"(score={best_score:.3f})"
            )
            return best_match

        if best_match:
            logger.debug(
                f"No match above threshold: '{text}' "
                f"(best={best_match.id}, score={best_score:.3f})"
            )
        return None
