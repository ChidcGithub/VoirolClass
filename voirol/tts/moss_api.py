import io
import threading
import time
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf

from voirol.tts.engine import TTSEngine
from voirol.utils.logger import get_logger

logger = get_logger("tts.moss_api")

_MOSS_VOICES = [
    "Xiaoyu", "Junhao", "Zhiming", "Weiguo", "Yuewen", "Lingyu",
    "Ava", "Bella", "Adam", "Nathan", "Trump",
    "Sakura", "Yui", "Aoi", "Hina", "Mei",
]


class MossApiEngine(TTSEngine):
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        voice: str = "Xiaoyu",
        timeout: int = 30,
    ):
        self._base_url = f"http://{host}:{port}"
        self._voice = voice
        self._timeout = timeout
        self._session = requests.Session()
        self._ready = False

    @property
    def voice(self) -> str:
        return self._voice

    @voice.setter
    def voice(self, value: str) -> None:
        self._voice = value

    @staticmethod
    def list_voices() -> list[str]:
        return list(_MOSS_VOICES)

    def load(self) -> bool:
        try:
            r = self._session.get(
                f"{self._base_url}/api/warmup-status",
                timeout=5,
            )
            data = r.json()
            if data.get("state") == "ready":
                self._ready = True
                logger.info("MOSS-TTS-Nano server is ready")
                return True
            logger.warning(f"MOSS-TTS-Nano server state: {data.get('state')}")
            self._ready = False
            return False
        except Exception as e:
            logger.warning(f"MOSS-TTS-Nano server not reachable: {e}")
            self._ready = False
            return False

    def unload(self) -> None:
        self._session.close()
        self._ready = False
        logger.info("MOSS-TTS-Nano client unloaded")

    def is_ready(self) -> bool:
        return self._ready

    def synthesize(self, text: str) -> np.ndarray:
        if not self._ready:
            raise RuntimeError("TTS engine not ready")
        try:
            r = self._session.post(
                f"{self._base_url}/api/synthesize",
                data={
                    "text": text,
                    "voice": self._voice,
                    "mode": "voice_clone",
                },
                timeout=self._timeout,
            )
            r.raise_for_status()
            audio, sr = sf.read(io.BytesIO(r.content))
            sd.play(audio, sr)
            sd.wait()
            return np.asarray(audio)
        except Exception as e:
            logger.error(f"MOSS-TTS-Nano synthesize failed: {e}")
            raise

    def synthesize_async(self, text: str) -> None:
        threading.Thread(target=self._play_async, args=(text,), daemon=True).start()

    def _play_async(self, text: str) -> None:
        try:
            self.synthesize(text)
        except Exception as e:
            logger.error(f"Async TTS playback failed: {e}")


__all__ = ["MossApiEngine", "_MOSS_VOICES"]
