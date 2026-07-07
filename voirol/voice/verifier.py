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


def _embed_with_extra_inputs(embedder, audio: np.ndarray) -> np.ndarray:
    """Handle ONNX models that require extra inputs (sr, h, c) beyond the
    primary feature tensor, by constructing the feed dict manually."""
    from speakeronnx.embedder import compute_fbank

    entry = embedder.entry
    session = embedder._session
    onnx_inputs = session.get_inputs()
    primary_name = onnx_inputs[0].name

    # Compute features (same logic as speakeronnx embed())
    if entry is None or entry.frontend == "fbank80":
        feats = compute_fbank(
            audio,
            sample_rate=embedder.sample_rate,
            num_mel_bins=entry.num_mel_bins if entry else 80,
            frame_length_ms=entry.frame_length_ms if entry else 25.0,
            frame_shift_ms=entry.frame_shift_ms if entry else 10.0,
            dither=0.0,
            apply_cmn=True,
        )
    elif entry.frontend == "raw":
        feats = audio
    else:
        raise ValueError(f"Unknown frontend: {entry.frontend!r}")

    # Shape the input
    if entry and entry.frontend == "raw":
        feats_in = feats[np.newaxis, np.newaxis, :].astype(np.float32)
    elif entry and entry.input_layout == "BFT":
        feats_in = feats.T[np.newaxis, :, :].astype(np.float32)
    else:
        feats_in = feats[np.newaxis, :, :].astype(np.float32)

    # Build feed dict with all required inputs
    feed_dict = {}
    for inp in onnx_inputs:
        if inp.name == primary_name:
            feed_dict[inp.name] = feats_in
        elif inp.name == "sr":
            feed_dict[inp.name] = np.array([embedder.sample_rate], dtype=np.int64)
        elif inp.name in ("h", "c"):
            shape = tuple(d if isinstance(d, (int, float)) and d > 0 else 1 for d in inp.shape)
            feed_dict[inp.name] = np.zeros(shape, dtype=np.float32)
        else:
            shape = tuple(d if isinstance(d, (int, float)) and d > 0 else 1 for d in inp.shape)
            feed_dict[inp.name] = np.zeros(shape, dtype=np.float32)

    if hasattr(embedder, "_output_name"):
        output_name = embedder._output_name
    else:
        output_name = session.get_outputs()[0].name

    out = session.run([output_name], feed_dict)
    emb = out[0].ravel().astype(np.float32)

    norm = np.linalg.norm(emb)
    if norm > 0:
        emb /= norm
    return emb


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
    try:
        emb = embedder.embed(audio)
    except ValueError as e:
        msg = str(e)
        if "missing from input feed" in msg or "Required inputs" in msg:
            logger.warning(
                "ONNX model requires extra inputs (%s), using manual feed dict", msg
            )
            emb = _embed_with_extra_inputs(embedder, audio)
        else:
            raise
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
