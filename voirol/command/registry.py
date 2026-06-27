from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Command:
    id: str
    keywords: list[str]
    description: str
    action: Callable[[], None]


@dataclass
class CommandRegistry:
    _commands: dict[str, Command] = field(default_factory=dict)

    def register(self, command: Command):
        self._commands[command.id] = command

    def get(self, command_id: str) -> Command | None:
        return self._commands.get(command_id)

    def get_all(self) -> list[Command]:
        return list(self._commands.values())

    def unregister(self, command_id: str):
        self._commands.pop(command_id, None)
