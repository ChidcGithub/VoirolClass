from abc import ABC, abstractmethod

import numpy as np


class ASREngine(ABC):
    @abstractmethod
    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...

    @abstractmethod
    def load(self):
        ...

    @abstractmethod
    def unload(self):
        ...
