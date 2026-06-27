import os

from voirol.utils.download import download_file
from voirol.utils.logger import get_logger

logger = get_logger("voice.models")

MODEL_URLS = {
    "silero_vad": (
        "https://gitee.com/nicethemes/silero-vad/raw/master/src/"
        "silero_vad/data/silero_vad.onnx"
    ),
}

MODEL_MIRROR_URLS = {
    "silero_vad": [
        "https://github.com/snakers4/silero-vad/raw/master/src/"
        "silero_vad/data/silero_vad.onnx",
        "https://githubfast.com/snakers4/silero-vad/raw/master/src/"
        "silero_vad/data/silero_vad.onnx",
    ],
}


def ensure_silero_vad(model_dir: str = "models") -> str:
    url = MODEL_URLS["silero_vad"]
    mirrors = MODEL_MIRROR_URLS.get("silero_vad", [])
    try:
        return download_file(
            url=url,
            dest_path=model_dir,
            filename="silero_vad.onnx",
            desc="Silero VAD model",
            mirrors=mirrors,
            timeout=60,
            retries=3,
        )
    except Exception as e:
        logger.error(f"Failed to download Silero VAD model: {e}")
        raise
