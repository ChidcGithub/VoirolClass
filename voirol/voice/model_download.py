import os
import shutil
import tarfile
import threading
import zipfile
from dataclasses import dataclass, field

import requests

from voirol.utils.download import download_file
from voirol.utils.logger import get_logger

logger = get_logger("voice.model_download")


class DownloadState:
    MISSING = "missing"
    DOWNLOADED = "downloaded"
    AUTO = "auto"


@dataclass
class ModelEntry:
    id: str
    name: str
    size: str
    urls: list[str] = field(default_factory=list)
    dest_dir: str = ""
    filename: str = ""
    expected_files: list[str] = field(default_factory=list)
    extract: bool = False
    auto: bool = False


MODELS: dict[str, ModelEntry] = {
    "silero_vad": ModelEntry(
        id="silero_vad",
        name="Silero VAD",
        size="7 MB",
        urls=[
            "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
            "https://gitee.com/nicethemes/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx",
        ],
        dest_dir="models",
        filename="silero_vad.onnx",
        expected_files=["models/silero_vad.onnx"],
    ),
    "sensevoice": ModelEntry(
        id="sensevoice",
        name="SenseVoice",
        size="228 MB",
        urls=[
            "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2",
        ],
        dest_dir="models",
        filename="sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2",
        expected_files=["models/sensevoice/model.int8.onnx", "models/sensevoice/tokens.txt"],
        extract=True,
    ),
    "vosk_zh": ModelEntry(
        id="vosk_zh",
        name="Vosk (Chinese)",
        size="42 MB",
        urls=[
            "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip",
            "https://mirrors.ustc.edu.cn/vosk-models/vosk-model-small-cn-0.22.zip",
        ],
        dest_dir="models",
        filename="vosk_zh.zip",
        expected_files=["models/vosk/am/final.mdl"],
        extract=True,
    ),
    "vosk_en": ModelEntry(
        id="vosk_en",
        name="Vosk (English)",
        size="42 MB",
        urls=[
            "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "https://mirrors.ustc.edu.cn/vosk-models/vosk-model-small-en-us-0.15.zip",
        ],
        dest_dir="models",
        filename="vosk_en.zip",
        expected_files=["models/vosk/am/final.mdl"],
        extract=True,
    ),
    "campplus": ModelEntry(
        id="campplus",
        name="CAM++ Voiceprint",
        size="27 MB",
        auto=True,
    ),
}


def check_model_status(model_id: str) -> str:
    entry = MODELS.get(model_id)
    if not entry:
        return DownloadState.MISSING
    if entry.auto:
        return DownloadState.AUTO
    if entry.expected_files and all(os.path.exists(f) for f in entry.expected_files):
        return DownloadState.DOWNLOADED
    return DownloadState.MISSING


def test_mirror(url: str) -> tuple[bool, str]:
    try:
        resp = requests.head(url.rstrip("/") + "/", timeout=10, allow_redirects=True)
        return (resp.ok, f"HTTP {resp.status_code}")
    except requests.RequestException as e:
        return (False, str(e))


def _apply_mirror(original_url: str, mirror_url: str) -> str:
    if not mirror_url:
        return original_url
    return mirror_url.rstrip("/") + "/" + original_url.lstrip("/")


def download_model(model_id: str, mirror_url: str = "", progress_callback=None) -> bool:
    entry = MODELS.get(model_id)
    if not entry or entry.auto:
        return False

    try:
        dl_url = _apply_mirror(entry.urls[0], mirror_url)
        mirrors = [_apply_mirror(u, mirror_url) for u in entry.urls[1:]] if mirror_url else entry.urls[1:]

        dest = entry.dest_dir
        os.makedirs(dest, exist_ok=True)
        filepath = os.path.join(dest, entry.filename)

        download_file(
            url=dl_url,
            dest_path=dest,
            filename=entry.filename,
            desc=entry.name,
            mirrors=mirrors or None,
            timeout=120,
            retries=3,
            progress_callback=progress_callback,
        )

        if entry.extract:
            if progress_callback:
                progress_callback(0)
            _extract_model(entry, filepath)

        if progress_callback:
            progress_callback(100)
        return True

    except Exception as e:
        logger.error(f"Failed to download {entry.name}: {e}")
        return False


def _extract_model(entry: ModelEntry, filepath: str):
    dest = entry.dest_dir
    base = os.path.dirname(filepath) or "."

    if entry.id == "sensevoice":
        extract_dir = os.path.join(base, "_extracted_sv")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir, exist_ok=True)
        logger.info(f"Extracting {entry.filename}...")
        with tarfile.open(filepath, "r:bz2") as tar:
            tar.extractall(extract_dir)

        target = os.path.join(base, "sensevoice")
        items = os.listdir(extract_dir)
        if items:
            src = os.path.join(extract_dir, items[0])
            if os.path.isdir(src):
                if os.path.exists(target):
                    shutil.rmtree(target)
                os.rename(src, target)
            else:
                if os.path.exists(target):
                    shutil.rmtree(target)
                shutil.copytree(extract_dir, target)
        shutil.rmtree(extract_dir, ignore_errors=True)
        logger.info(f"SenseVoice extracted to {target}")

    elif entry.id.startswith("vosk"):
        logger.info(f"Extracting {entry.filename}...")
        with zipfile.ZipFile(filepath, "r") as zf:
            zf.extractall(base)

        target = os.path.join(base, "vosk")
        extracted = [
            d for d in os.listdir(base)
            if os.path.isdir(os.path.join(base, d))
            and d.startswith("vosk-model")
        ]
        if extracted:
            src = os.path.join(base, extracted[0])
            if os.path.exists(target):
                shutil.rmtree(target)
            os.rename(src, target)
            logger.info(f"Vosk extracted to {target}")

    os.remove(filepath)
