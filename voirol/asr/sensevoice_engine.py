import json
import os
import re
from pathlib import Path

import numpy as np
import onnxruntime as ort
from scipy.signal import spectrogram

from voirol.asr.engine import ASREngine
from voirol.utils.logger import get_logger

logger = get_logger("asr.sensevoice")

SENSEVOICE_MODEL_URLS = {
    "int8": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2",
}

SPECIAL_TAGS = {
    "<|zh|>", "<|en|>", "<|ja|>", "<|ko|>", "<|yue|>",
    "<|NEUTRAL|>", "<|HAPPY|>", "<|SAD|>", "<|ANGRY|>",
    "<|EMO_UNKNOWN|>",
    "<|Speech|>", "<|BGM|>", "<|Sing|>", "<|Noise|>", "<|Cry|>", "<|Laugh|>",
    "<|woitn|>", "<|withitn|>",
    "<|SPECIAL_TOKEN_0|>", "<|SPECIAL_TOKEN_1|>", "<|SPECIAL_TOKEN_2|>",
    "<|SPECIAL_TOKEN_3|>", "<|SPECIAL_TOKEN_4|>", "<|SPECIAL_TOKEN_5|>",
}


class SenseVoiceEngine(ASREngine):
    def __init__(
        self,
        model_dir: str = "models/sensevoice",
        num_threads: int = 2,
        language: str = "zh",
        use_itn: bool = False,
    ):
        self.model_dir = model_dir
        self.num_threads = num_threads
        self.language = language
        self.use_itn = use_itn
        self._session = None
        self._tokens: dict[int, bytes] = {}
        self._meta: dict[str, str] = {}
        self._lang_id = 0
        self._with_itn = 14
        self._without_itn = 15
        self._lfr_win = 7
        self._lfr_shift = 6
        self._feature_dim = 80
        self._neg_mean: np.ndarray | None = None
        self._inv_stddev: np.ndarray | None = None

    def is_ready(self) -> bool:
        return self._session is not None

    def _find_model_file(self) -> str:
        candidates = ["model.int8.onnx", "model_quant.onnx", "model.onnx"]
        for name in candidates:
            path = os.path.join(self.model_dir, name)
            if os.path.exists(path):
                return path
        raise FileNotFoundError(
            f"No ONNX model found in {self.model_dir}. "
            f"Looked for: {', '.join(candidates)}"
        )

    def load(self):
        model_path = self._find_model_file()
        token_path = os.path.join(self.model_dir, "tokens.txt")
        if not os.path.exists(token_path):
            raise FileNotFoundError(f"tokens.txt not found in {self.model_dir}")

        with open(token_path, "rb") as f:
            for line in f.read().split(b"\n"):
                parts = line.rsplit(b" ", 1)
                if len(parts) == 2:
                    self._tokens[int(parts[1])] = parts[0]

        so = ort.SessionOptions()
        so.intra_op_num_threads = self.num_threads
        so.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            model_path, providers=["CPUExecutionProvider"],
            sess_options=so,
        )

        cm = self._session.get_modelmeta().custom_metadata_map
        self._meta = dict(cm)

        self._lfr_win = int(cm.get("lfr_window_size", 7))
        self._lfr_shift = int(cm.get("lfr_window_shift", 6))
        self._feature_dim = int(cm.get("feature_dim", 80))
        if self._feature_dim <= 0 or self._feature_dim > 200:
            self._feature_dim = 80

        nm = cm.get("neg_mean", "")
        iv = cm.get("inv_stddev", "")
        if nm and iv:
            self._neg_mean = np.array(
                [float(v) for v in nm.split(",")], dtype=np.float32
            )
            self._inv_stddev = np.array(
                [float(v) for v in iv.split(",")], dtype=np.float32
            )

        lang_map = {"zh": "lang_zh", "en": "lang_en", "ja": "lang_ja",
                     "ko": "lang_ko", "yue": "lang_yue"}
        key = lang_map.get(self.language, "lang_auto")
        self._lang_id = int(cm.get(key, 0))

        self._with_itn = int(cm.get("with_itn", 14))
        self._without_itn = int(cm.get("without_itn", 15))

        logger.info(
            f"SenseVoice engine loaded (model={os.path.basename(model_path)}, "
            f"lang={self.language}(id={self._lang_id}), "
            f"lfr={self._lfr_win}/{self._lfr_shift})"
        )

    def unload(self):
        self._session = None
        self._tokens.clear()
        self._meta.clear()
        logger.info("SenseVoice engine unloaded")

    def _extract_fbank(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        audio = audio.flatten().astype(np.float32)
        n_fft = 512
        hop = 160
        win = 400
        f, t, Sxx = spectrogram(
            audio, fs=sample_rate,
            nperseg=win, noverlap=win - hop, nfft=n_fft,
        )

        n_mels = self._feature_dim
        mel_min, mel_max = 0.0, sample_rate / 2.0
        mel_pts = np.linspace(
            2595 * np.log10(1 + mel_min / 700),
            2595 * np.log10(1 + mel_max / 700),
            n_mels + 2,
        )
        hz_pts = 700 * (10 ** (mel_pts / 2595) - 1)
        bins = np.floor((n_fft + 1) * hz_pts / sample_rate).astype(int)
        bins = np.clip(bins, 0, n_fft // 2)

        fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
        for m_ in range(1, n_mels + 1):
            l, c_, r = bins[m_ - 1], bins[m_], bins[m_ + 1]
            for k in range(l, c_):
                fb[m_ - 1, k] = (k - l) / (c_ - l) if c_ > l else 0.0
            for k in range(c_, r):
                fb[m_ - 1, k] = (r - k) / (r - c_) if r > c_ else 0.0

        mel_spec = fb @ Sxx
        mel_spec = np.maximum(mel_spec, 1e-10)
        log_mel = np.log(mel_spec).T
        return log_mel

    def _apply_lfr(self, fbank: np.ndarray) -> np.ndarray:
        T = fbank.shape[0]
        dim = self._feature_dim
        win = self._lfr_win
        shift = self._lfr_shift
        pad = (win - 1) // 2
        padded = np.pad(fbank, ((pad, win - 1 - pad), (0, 0)), mode="edge")

        frames = []
        t = 0
        while t < T:
            end = min(t + win, padded.shape[0])
            frame = padded[t:end].flatten()
            if len(frame) < dim * win:
                frame = np.pad(frame, (0, dim * win - len(frame)))
            frames.append(frame)
            t += shift

        return np.array(frames, dtype=np.float32)

    def _decode_ctc(self, logits: np.ndarray) -> list[int]:
        probs = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
        probs /= np.sum(probs, axis=-1, keepdims=True)
        ids = np.argmax(probs[0], axis=-1)

        prev = -1
        result = []
        for id_ in ids.tolist():
            if id_ != prev and id_ != 0:
                result.append(id_)
            prev = id_
        return result

    def _strip_special_tags(self, ids: list[int]) -> list[int]:
        result = []
        found_speech = False
        for id_ in ids:
            token_str = self._tokens.get(id_, b"").decode("utf-8", errors="replace")
            if not found_speech:
                if token_str in SPECIAL_TAGS:
                    continue
                found_speech = True
            result.append(id_)
        return result

    def _ids_to_text(self, ids: list[int]) -> str:
        result_bytes = b"".join(
            self._tokens.get(i, b"") for i in ids
        )
        result_bytes = result_bytes.replace(b"\xe2\x96\x81", b" ")
        try:
            return result_bytes.decode("utf-8").strip()
        except UnicodeDecodeError:
            return result_bytes.decode("utf-8", errors="replace").strip()

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if not self.is_ready():
            raise RuntimeError("SenseVoice engine not loaded")

        if len(audio) < sample_rate * 0.1:
            return ""

        fbank = self._extract_fbank(audio, sample_rate)
        if fbank.shape[0] < 3:
            return ""

        lfr = self._apply_lfr(fbank)
        if self._neg_mean is not None and self._inv_stddev is not None:
            lfr = (lfr + self._neg_mean) * self._inv_stddev

        text_norm = self._with_itn if self.use_itn else self._without_itn
        language = np.array([self._lang_id], dtype=np.int32)

        outs = self._session.run(None, {
            "x": lfr[np.newaxis, :, :].astype(np.float32),
            "x_length": np.array([lfr.shape[0]], dtype=np.int32),
            "language": language,
            "text_norm": np.array([text_norm], dtype=np.int32),
        })
        logits = outs[0]

        ids = self._decode_ctc(logits)
        ids = self._strip_special_tags(ids)
        text = self._ids_to_text(ids)

        if text:
            logger.debug(f"ASR result: '{text}'")
        return text
