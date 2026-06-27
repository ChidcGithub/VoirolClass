import json

from voirol.ai.engine import AIEngine
from voirol.command.registry import CommandRegistry
from voirol.utils.i18n import t
from voirol.utils.logger import get_logger

logger = get_logger("ai.matcher")

DEFAULT_SYSTEM_PROMPT = """You are a command matching assistant for a voice-controlled classroom system.
Match the user's speech to the most appropriate command from the list below.
Return ONLY a JSON object with no extra text.

Available commands:
{commands_list}

Rules:
- The user said: "{user_text}"
- If intent clearly matches a command, return {{"command": "command_id"}}
- If unclear or no match, return {{"command": null}}
- Be conservative: only match when confident
- Consider synonyms and paraphrasing in both Chinese and English"""


def _build_commands_list(registry: CommandRegistry) -> str:
    lines = []
    for cmd in registry.get_all():
        keywords = " / ".join(cmd.keywords[:4])
        lines.append(f"- {cmd.id}: {keywords}")
    return "\n".join(lines)


class AIMatcher:
    def __init__(
        self,
        engine: AIEngine | None,
        registry: CommandRegistry,
        system_prompt: str = "",
        temperature: float = 0.1,
        timeout: int = 10,
    ):
        self.engine = engine
        self.registry = registry
        self._system_prompt = system_prompt
        self.temperature = temperature
        self.timeout = timeout

    @property
    def system_prompt(self) -> str:
        return self._system_prompt

    @system_prompt.setter
    def system_prompt(self, value: str):
        self._system_prompt = value

    def match(self, text: str) -> object | None:
        if self.engine is None:
            return None

        commands_str = _build_commands_list(self.registry)
        prompt = (self._system_prompt or DEFAULT_SYSTEM_PROMPT)
        try:
            prompt = prompt.format(commands_list=commands_str, user_text=text)
        except KeyError:
            prompt = DEFAULT_SYSTEM_PROMPT.format(commands_list=commands_str, user_text=text)

        messages = [
            {"role": "system", "content": prompt},
        ]

        try:
            raw = self.engine.chat(messages, self.temperature, self.timeout)
            if not raw:
                return None

            data = json.loads(raw)
            cmd_id = data.get("command")
            if not cmd_id:
                logger.info(f"AI: no match for '{text}'")
                return None

            cmd = self.registry.get(cmd_id)
            if cmd is None:
                logger.warning(f"AI returned unknown command: {cmd_id}")
                return None

            logger.info(f"AI matched '{text}' -> {cmd_id}")
            return cmd

        except json.JSONDecodeError:
            logger.warning(f"AI response not valid JSON: {raw}")
            return None
        except Exception as e:
            logger.warning(f"AI match error: {e}")
            return None
