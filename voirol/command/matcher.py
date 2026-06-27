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
