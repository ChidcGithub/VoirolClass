import threading

import numpy as np
from speakeronnx import SpeakerEmbedder

from voirol.utils.logger import get_logger
from voirol.voice.enrollment import SpeakerProfile

logger = get_logger("voice.verifier")

DEFAULT_MODEL = "campplus-zh-en"
DEFAULT_THRESHOLD = 0.45

_EMBEDDER = None
_EMBEDDER_KEY = None
_EMBEDDER_LOCK = threading.Lock()


def _get_embedder(model_path: str = None):
    global _EMBEDDER, _EMBEDDER_KEY
    key = model_path or DEFAULT_MODEL
    with _EMBEDDER_LOCK:
        if _EMBEDDER is None or key != _EMBEDDER_KEY:
            _EMBEDDER_KEY = key
            _EMBEDDER = SpeakerEmbedder(model=key)
            logger.info(f"Speaker embedder loaded: {key}")
    return _EMBEDDER


def extract_embedding(
    audio: np.ndarray,
    sample_rate: int = 16000,
    model_path: str = None,
    tag: str = "",
) -> np.ndarray:
    embedder = _get_embedder(model_path)
    if sample_rate != embedder.sample_rate:
        from scipy import signal
        n = int(len(audio) * embedder.sample_rate / sample_rate)
        audio = signal.resample(audio, n).astype(np.float32)
    emb = embedder.embed(audio)
    if tag:
        print(f"[DEBUG {tag}] emb_dim={len(emb)}, first5={emb[:5].round(4).tolist()}, "
              f"norm={np.linalg.norm(emb):.4f}")
    return emb


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a.ravel(), b.ravel()))


class SpeakerVerifier:
    def __init__(self, threshold: float = DEFAULT_THRESHOLD, model_path: str = None):
        self.threshold = threshold
        self._model_path = model_path or DEFAULT_MODEL
        self._profile: SpeakerProfile | None = None
        self._lock = threading.Lock()
        _get_embedder(self._model_path)
        logger.info(
            f"SpeakerVerifier initialized (threshold={threshold}, model={self._model_path})"
        )

    def set_profile(self, profile: SpeakerProfile | None):
        with self._lock:
            self._profile = profile
        if profile:
            logger.info(f"Active profile set to: {profile.name}")

    def get_active_name(self) -> str | None:
        with self._lock:
            return self._profile.name if self._profile else None

    def verify(
        self, audio: np.ndarray, sample_rate: int = 16000
    ) -> tuple[bool, float]:
        with self._lock:
            profile = self._profile
        if profile is None:
            logger.warning("No active profile for verification")
            return False, 0.0

        if len(audio) < sample_rate * 0.3:
            logger.debug("Audio too short for verification")
            return False, 0.0

        embedding = extract_embedding(audio, sample_rate, self._model_path, tag="verify")

        if len(embedding) != len(profile.embedding):
            logger.warning(
                f"Embedding dimension mismatch: profile="
                f"{len(profile.embedding)}, "
                f"live={len(embedding)}. Please re-enroll this teacher."
            )
            return False, 0.0

        similarity = cosine_similarity(embedding, profile.embedding)
        is_match = similarity >= self.threshold

        logger.debug(
            f"Verification: similarity={similarity:.4f}, "
            f"threshold={self.threshold}, match={is_match}"
        )
        return is_match, similarity


def create_profile_from_audio(
    audio_files: list[np.ndarray],
    name: str,
    sample_rate: int = 16000,
    model_path: str = None,
) -> SpeakerProfile:
    embeddings = []
    for idx, audio in enumerate(audio_files):
        emb = extract_embedding(audio, sample_rate, model_path, tag=f"enroll_{idx}")
        embeddings.append(emb)

    avg_embedding = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(avg_embedding)
    if norm > 1e-10:
        avg_embedding = avg_embedding / norm

    print(f"[DEBUG profile] avg_norm_before_l2={norm:.4f}, "
          f"first5={avg_embedding[:5].round(4).tolist()}")

    logger.info(
        f"Created profile '{name}' from {len(audio_files)} utterances, "
        f"embedding dim={len(avg_embedding)}"
    )
    return SpeakerProfile(
        name=name,
        embedding=avg_embedding,
        utterances=len(audio_files),
    )
