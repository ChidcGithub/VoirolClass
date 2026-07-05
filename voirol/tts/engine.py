from abc import ABC, abstractmethod

import numpy as np


class TTSEngine(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> np.ndarray:
        ...

    @abstractmethod
    def synthesize_async(self, text: str) -> None:
        ...

    @abstractmethod
    def load(self) -> bool:
        ...

    @abstractmethod
    def unload(self) -> None:
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...


__all__ = ["TTSEngine"]
