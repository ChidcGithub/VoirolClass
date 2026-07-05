import os
import shutil
import tarfile
from dataclasses import dataclass, field

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from voirol.utils.download import download_file
from voirol.utils.logger import get_logger

logger = get_logger("voice.model_download")


DOWNLOAD_ORDER = ["silero_vad", "sensevoice"]
QUEUE_FILE = "data/.download_queue"


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


PORTABLE_PYTHON_URL = (
    "https://github.com/astral-sh/python-build-standalone/releases/download/20250115/"
    "cpython-3.12.8+20250115-x86_64-pc-windows-msvc-install_only.tar.gz"
)

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
    "campplus": ModelEntry(
        id="campplus",
        name="CAM++ Voiceprint",
        size="27 MB",
        auto=True,
    ),
    "moss_tts_nano": ModelEntry(
        id="moss_tts_nano",
        name="MOSS-TTS-Nano-100M",
        size="2.2 GB",
        urls=[
            "https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M/resolve/main/pytorch_model.bin",
        ],
        dest_dir="models/moss-tts-nano",
        filename="pytorch_model.bin",
        expected_files=["models/moss-tts-nano/pytorch_model.bin", "models/moss-tts-nano/config.json"],
        extract=False,
    ),
    "moss_audio_tokenizer": ModelEntry(
        id="moss_audio_tokenizer",
        name="MOSS-Audio-Tokenizer-Nano",
        size="500 MB",
        urls=[
            "https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano/resolve/main/model-00001-of-00001.safetensors",
        ],
        dest_dir="models/moss-audio-tokenizer-nano",
        filename="model-00001-of-00001.safetensors",
        expected_files=["models/moss-audio-tokenizer-nano/model-00001-of-00001.safetensors", "models/moss-audio-tokenizer-nano/config.json"],
        extract=False,
    ),
    "portable_python": ModelEntry(
        id="portable_python",
        name="Portable Python 3.12",
        size="30 MB",
        urls=[PORTABLE_PYTHON_URL],
        dest_dir="runtime",
        filename="python.tar.gz",
        expected_files=["runtime/python/python.exe"],
        extract=True,
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


def _apply_mirror(original_url: str, mirror_url: str, hf_mirror_url: str = "") -> str:
    if "huggingface.co" in original_url:
        if hf_mirror_url:
            domain = hf_mirror_url.rstrip("/").replace("https://", "").replace("http://", "")
            return original_url.replace("huggingface.co", domain)
        return original_url
    if not mirror_url:
        return original_url
    if not any(domain in original_url for domain in ["github.com", "raw.githubusercontent.com"]):
        return original_url
    return mirror_url.rstrip("/") + "/" + original_url.lstrip("/")


def download_model(model_id: str, mirror_url: str = "", hf_mirror_url: str = "", progress_callback=None) -> bool:
    entry = MODELS.get(model_id)
    if not entry or entry.auto:
        return False

    try:
        dl_url = _apply_mirror(entry.urls[0], mirror_url, hf_mirror_url)
        mirrors = [_apply_mirror(u, mirror_url, hf_mirror_url) for u in entry.urls[1:]] if mirror_url else entry.urls[1:]

        dest = entry.dest_dir
        os.makedirs(dest, exist_ok=True)
        filepath = os.path.join(dest, entry.filename)

        archive_type = "tar"

        download_file(
            url=dl_url,
            dest_path=dest,
            filename=entry.filename,
            desc=entry.name,
            mirrors=mirrors or None,
            timeout=120,
            retries=3,
            progress_callback=progress_callback,
            archive_type=archive_type,
        )

        if entry.extract:
            if progress_callback:
                progress_callback(-1)
            _extract_model(entry, filepath, progress_callback)

        if progress_callback:
            progress_callback(100)
        return True

    except Exception as e:
        logger.error(f"Failed to download {entry.name}: {e}")
        return False


def _detect_tar_mode(filename: str) -> str:
    if filename.endswith(".tar.bz2"):
        return "r:bz2"
    elif filename.endswith(".tar.gz") or filename.endswith(".tgz"):
        return "r:gz"
    return "r:"


def _extract_model(entry: ModelEntry, filepath: str, progress_callback=None):
    base = os.path.dirname(filepath) or "."
    logger.info(f"Extracting {entry.filename}...")

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Archive not found: {filepath}")
    if not tarfile.is_tarfile(filepath):
        raise ValueError(f"Not a valid tar file: {filepath}")

    mode = _detect_tar_mode(entry.filename)

    if entry.id == "sensevoice":
        extract_dir = os.path.join(base, "_extracted_sv")
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)
        os.makedirs(extract_dir, exist_ok=True)

        with tarfile.open(filepath, mode) as tar:
            members = tar.getmembers()
            total = len(members)
            for i, m in enumerate(members):
                tar.extract(m, extract_dir)
                if progress_callback:
                    pct = int((i + 1) / total * 90)
                    progress_callback(pct)

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
    else:
        dest = entry.dest_dir
        os.makedirs(dest, exist_ok=True)
        with tarfile.open(filepath, mode) as tar:
            members = tar.getmembers()
            total = len(members)
            for i, m in enumerate(members):
                tar.extract(m, dest)
                if progress_callback:
                    pct = int((i + 1) / total * 90)
                    progress_callback(pct)
        logger.info(f"Extracted {entry.filename} to {dest}")

    if progress_callback:
        progress_callback(95)
    os.remove(filepath)


def save_queue(model_ids: list[str]):
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(model_ids))


def load_queue() -> list[str]:
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        ids = [line.strip() for line in f if line.strip()]
    return ids


def clear_queue():
    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)


class DownloadWorker(QObject):
    progress = pyqtSignal(str, int)
    model_finished = pyqtSignal(str, bool)
    all_finished = pyqtSignal()

    def __init__(self, model_ids: list[str], mirror_url: str = "", hf_mirror_url: str = ""):
        super().__init__()
        self.model_ids = model_ids
        self.mirror_url = mirror_url
        self.hf_mirror_url = hf_mirror_url

    def run(self):
        for mid in self.model_ids:
            ok = download_model(
                mid, self.mirror_url, self.hf_mirror_url,
                progress_callback=lambda p: self.progress.emit(mid, p),
            )
            self.model_finished.emit(mid, ok)
        self.all_finished.emit()
