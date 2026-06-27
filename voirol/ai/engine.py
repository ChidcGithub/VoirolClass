from abc import ABC, abstractmethod


class AIEngine(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], temperature: float, timeout: int) -> str | None:
        ...
