import json
import os
import zipfile

import numpy as np

from voirol.asr.engine import ASREngine
from voirol.utils.download import download_file
from voirol.utils.logger import get_logger

logger = get_logger("asr.vosk")

VOSK_MODEL_URLS = {
    "zh-cn": (
        "https://mirrors.ustc.edu.cn/vosk-models/"
        "vosk-model-small-cn-0.22.zip"
    ),
    "en-us": (
        "https://mirrors.ustc.edu.cn/vosk-models/"
        "vosk-model-small-en-us-0.15.zip"
    ),
}

VOSK_MIRROR_URLS = {
    "zh-cn": [
        "https://alphacephei.com/vosk/models/"
        "vosk-model-small-cn-0.22.zip",
    ],
    "en-us": [
        "https://alphacephei.com/vosk/models/"
        "vosk-model-small-en-us-0.15.zip",
    ],
}


class VoskEngine(ASREngine):
    def __init__(self, model_path: str = "models/vosk", language: str = "zh-cn"):
        self.model_path = model_path
        self.language = language
        self._model = None
        self._rec = None

    def is_ready(self) -> bool:
        return self._model is not None and self._rec is not None

    def _ensure_model(self):
        if os.path.exists(self.model_path) and os.listdir(self.model_path):
            return

        url = VOSK_MODEL_URLS.get(self.language)
        mirrors = VOSK_MIRROR_URLS.get(self.language, [])
        if not url:
            raise ValueError(f"Unsupported language: {self.language}")

        parent = os.path.dirname(self.model_path) or "."
        zip_path = os.path.join(parent, f"vosk_{self.language}.zip")

        try:
            download_file(
                url=url,
                dest_path=parent,
                filename=os.path.basename(zip_path),
                desc=f"Vosk model ({self.language})",
                mirrors=mirrors,
                timeout=120,
                retries=3,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to download Vosk model for {self.language}. "
                f"Manual download: {url}" 
            ) from e

        logger.info("Extracting Vosk model...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(parent)

        extracted = [
            d
            for d in os.listdir(parent)
            if os.path.isdir(os.path.join(parent, d))
            and d.startswith("vosk-model")
        ]
        if extracted:
            src = os.path.join(parent, extracted[0])
            if os.path.exists(self.model_path):
                import shutil

                shutil.rmtree(self.model_path)
            os.rename(src, self.model_path)

        os.remove(zip_path)
        logger.info(f"Vosk model ready at {self.model_path}")

    def load(self):
        try:
            from vosk import KaldiRecognizer, Model
        except ImportError:
            raise ImportError("Vosk not installed. Run: pip install vosk")

        self._ensure_model()
        self._model = Model(self.model_path)
        self._rec = KaldiRecognizer(self._model, 16000)
        self._rec.SetWords(True)
        logger.info("Vosk engine loaded")

    def unload(self):
        self._model = None
        self._rec = None
        logger.info("Vosk engine unloaded")

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if not self.is_ready():
            raise RuntimeError("Vosk engine not loaded")

        if sample_rate != 16000:
            raise ValueError("Vosk requires 16kHz audio")

        audio_int16 = (audio * 32767).astype(np.int16).tobytes()
        self._rec.AcceptWaveform(audio_int16)

        result = json.loads(self._rec.Result())
        text = result.get("text", "").strip()

        if text:
            logger.debug(f"ASR result: '{text}'")
        return text

    def transcribe_partial(self, audio_chunk: np.ndarray) -> str:
        if not self.is_ready():
            return ""

        chunk_int16 = (audio_chunk * 32767).astype(np.int16).tobytes()
        if self._rec.AcceptWaveform(chunk_int16):
            result = json.loads(self._rec.Result())
            return result.get("text", "").strip()
        else:
            partial = json.loads(self._rec.PartialResult())
            return partial.get("partial", "").strip()
