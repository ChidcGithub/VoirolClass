import wave
import io

import numpy as np
import requests

from voirol.asr.engine import ASREngine, asr_audio_to_int16
from voirol.utils.logger import get_logger

logger = get_logger("asr.azure")


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class AzureEngine(ASREngine):
    def __init__(self, subscription_key: str, region: str, language: str = "zh"):
        self._subscription_key = subscription_key
        self._region = region
        self._lang = "zh-CN" if language.startswith("zh") else "en-US"
        self._ready = False

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        audio_int16 = asr_audio_to_int16(audio)

        pcm_bytes = audio_int16.tobytes()
        wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate)

        url = (
            f"https://{self._region}.stt.speech.microsoft.com"
            f"/speech/recognition/conversation/cognitiveservices/v1"
            f"?language={self._lang}"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": self._subscription_key,
            "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000",
        }

        try:
            resp = requests.post(url, data=wav_bytes, headers=headers, timeout=30)
            data = resp.json()
            status = data.get("RecognitionStatus", "Error")
            if status == "Success":
                text = data.get("DisplayText", "")
                return text.strip()

            logger.warning(f"Azure ASR status: {status}")
            return ""
        except Exception as e:
            logger.warning(f"Azure ASR request failed: {e}")
            return ""

    def load(self):
        self._ready = True

    def unload(self):
        self._ready = False

    def is_ready(self) -> bool:
        return self._ready
