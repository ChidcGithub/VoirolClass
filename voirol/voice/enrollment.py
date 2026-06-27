import os
import pickle
from dataclasses import dataclass, field

import numpy as np
import soundfile as sf

from voirol.utils.logger import get_logger

logger = get_logger("voice.enrollment")


@dataclass
class SpeakerProfile:
    name: str
    embedding: np.ndarray
    utterances: int = 0


@dataclass
class EnrollmentManager:
    enrollment_dir: str = "data/enrollments"
    _profiles: dict[str, SpeakerProfile] = field(default_factory=dict)

    def __post_init__(self):
        os.makedirs(self.enrollment_dir, exist_ok=True)
        self._load_all()

    def _profile_path(self, name: str) -> str:
        return os.path.join(self.enrollment_dir, f"{name}.pkl")

    def _load_all(self):
        if not os.path.isdir(self.enrollment_dir):
            return
        for fname in os.listdir(self.enrollment_dir):
            if fname.endswith(".pkl"):
                path = os.path.join(self.enrollment_dir, fname)
                try:
                    with open(path, "rb") as f:
                        profile = pickle.load(f)
                    self._profiles[profile.name] = profile
                    logger.info(f"Loaded profile: {profile.name}")
                except Exception as e:
                    logger.warning(f"Failed to load {fname}: {e}")

    def save_profile(self, profile: SpeakerProfile):
        path = self._profile_path(profile.name)
        with open(path, "wb") as f:
            pickle.dump(profile, f)
        self._profiles[profile.name] = profile
        logger.info(f"Saved profile: {profile.name}")

    def get_profile(self, name: str) -> SpeakerProfile | None:
        return self._profiles.get(name)

    def list_profiles(self) -> list[str]:
        return list(self._profiles.keys())

    def delete_profile(self, name: str):
        path = self._profile_path(name)
        if os.path.exists(path):
            os.remove(path)
        self._profiles.pop(name, None)
        logger.info(f"Deleted profile: {name}")

    def delete_all_profiles(self):
        for name in list(self._profiles.keys()):
            self.delete_profile(name)

    def save_enrollment_audio(
        self, teacher_name: str, utterance_idx: int, audio: np.ndarray, sample_rate: int
    ) -> str:
        dir_path = os.path.join(self.enrollment_dir, teacher_name)
        os.makedirs(dir_path, exist_ok=True)
        path = os.path.join(dir_path, f"utterance_{utterance_idx}.wav")
        sf.write(path, audio, sample_rate)
        return path
