import numpy as np
from scipy import signal


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        return audio / max_val
    return audio


def remove_dc_offset(audio: np.ndarray) -> np.ndarray:
    return audio - np.mean(audio)


def bandpass_filter(
    audio: np.ndarray,
    sample_rate: int = 16000,
    low: int = 80,
    high: int = 7600,
    order: int = 5,
) -> np.ndarray:
    nyquist = sample_rate / 2
    sos = signal.butter(
        order, [low / nyquist, high / nyquist], btype="band", output="sos"
    )
    return signal.sosfilt(sos, audio)


def preprocess(
    audio: np.ndarray,
    sample_rate: int = 16000,
    normalize: bool = True,
    remove_dc: bool = True,
    filter_bp: bool = False,
) -> np.ndarray:
    audio = audio.copy().flatten()
    if remove_dc:
        audio = remove_dc_offset(audio)
    if filter_bp:
        audio = bandpass_filter(audio, sample_rate)
    if normalize:
        audio = normalize_audio(audio)
    return audio


def frame_energy(audio: np.ndarray, frame_size: int = 512) -> float:
    if len(audio) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio**2)))
