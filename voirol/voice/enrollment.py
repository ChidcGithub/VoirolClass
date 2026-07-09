import json
import os
import threading
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf

from voirol.utils.logger import get_logger

logger = get_logger("voice.enrollment")


def _np_to_list(arr: np.ndarray) -> list:
    return arr.tolist() if isinstance(arr, np.ndarray) else arr


def _list_to_np(lst: list) -> np.ndarray:
    return np.array(lst, dtype=np.float32)


@dataclass
class SpeakerProfile:
    name: str
    embedding: np.ndarray
    utterances: int = 0


@dataclass
class EnrollmentManager:
    enrollment_dir: str = "data/enrollments"
    _profiles: dict[str, SpeakerProfile] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        os.makedirs(self.enrollment_dir, exist_ok=True)
        self._load_all()

    def _profile_path(self, name: str) -> str:
        return os.path.join(self.enrollment_dir, f"{name}.json")

    def _load_all(self):
        if not os.path.isdir(self.enrollment_dir):
            return
        for fname in os.listdir(self.enrollment_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.enrollment_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    profile = SpeakerProfile(
                        name=data["name"],
                        embedding=_list_to_np(data["embedding"]),
                        utterances=data.get("utterances", 0),
                    )
                    self._profiles[profile.name] = profile
                    logger.info(f"Loaded profile: {profile.name}")
                except Exception as e:
                    logger.warning(f"Failed to load {fname}: {e}")
            if fname.endswith(".pkl"):
                path = os.path.join(self.enrollment_dir, fname)
                try:
                    with open(path, "rb") as f:
                        import pickle
                        profile = pickle.load(f)
                    self._profiles[profile.name] = profile
                    logger.info(f"Loaded legacy profile: {profile.name}")
                except Exception as e:
                    logger.warning(f"Failed to load legacy {fname}: {e}")

    def save_profile(self, profile: SpeakerProfile):
        path = self._profile_path(profile.name)
        data = {
            "name": profile.name,
            "embedding": _np_to_list(profile.embedding),
            "utterances": profile.utterances,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        with self._lock:
            self._profiles[profile.name] = profile
        logger.info(f"Saved profile: {profile.name}")

    def get_profile(self, name: str) -> SpeakerProfile | None:
        with self._lock:
            return self._profiles.get(name)

    def list_profiles(self) -> list[str]:
        with self._lock:
            return list(self._profiles.keys())

    def delete_profile(self, name: str):
        path = self._profile_path(name)
        if os.path.exists(path):
            os.remove(path)
        legacy = os.path.join(self.enrollment_dir, f"{name}.pkl")
        if os.path.exists(legacy):
            os.remove(legacy)
        with self._lock:
            self._profiles.pop(name, None)
        logger.info(f"Deleted profile: {name}")

    def delete_all_profiles(self):
        with self._lock:
            names = list(self._profiles.keys())
        for name in names:
            path = self._profile_path(name)
            if os.path.exists(path):
                os.remove(path)
            legacy = os.path.join(self.enrollment_dir, f"{name}.pkl")
            if os.path.exists(legacy):
                os.remove(legacy)
        with self._lock:
            for name in names:
                self._profiles.pop(name, None)
            logger.info("Deleted all profiles")

    def save_enrollment_audio(
        self, teacher_name: str, utterance_idx: int, audio: np.ndarray, sample_rate: int
    ) -> str:
        dir_path = os.path.join(self.enrollment_dir, teacher_name)
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, f"utterance_{utterance_idx}.wav")
        sf.write(path, audio, sample_rate)
        return path
