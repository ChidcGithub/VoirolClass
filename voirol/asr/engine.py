from abc import ABC, abstractmethod

import numpy as np


def asr_audio_to_int16(audio: np.ndarray) -> np.ndarray:
    if audio.dtype != np.int16:
        return (audio * 32767).clip(-32768, 32767).astype(np.int16)
    return audio


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
