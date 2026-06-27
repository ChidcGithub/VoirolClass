import numpy as np
import onnxruntime

from voirol.utils.logger import get_logger

logger = get_logger("audio.vad")

SILERO_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/src/"
    "silero_vad/data/silero_vad.onnx"
)


class SileroVAD:
    def __init__(
        self,
        model_path: str = "models/silero_vad.onnx",
        threshold: float = 0.5,
        sample_rate: int = 16000,
        min_speech_duration: float = 0.5,
        silence_duration: float = 0.8,
    ):
        self.threshold = threshold
        self.sample_rate = sample_rate
        self.min_speech_frames = int(min_speech_duration * sample_rate / 512)
        self.silence_frames = int(silence_duration * sample_rate / 512)
        try:
            self._session = onnxruntime.InferenceSession(
                model_path, providers=["CPUExecutionProvider"]
            )
            self._input_names = [
                inp.name for inp in self._session.get_inputs()
            ]
            self._input_name = "input"
            self._sr_name = "sr"
            self._state_name = "state"
            if "input" not in self._input_names:
                self._input_name = self._input_names[0]
            if "sr" not in self._input_names:
                self._sr_name = self._input_names[1] if len(self._input_names) > 1 else self._input_names[0]
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            self._session = None
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context_size = 64
        self._context = np.zeros((1, self._context_size), dtype=np.float32)
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speech = False
        self._speech_start_frame = 0
        self._frame_count = 0
        logger.info(
            f"Silero VAD initialized (inputs: {self._input_names})"
        )

    def _validate_input(self, audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 2 and audio.shape[1] > 1:
            audio = np.mean(audio, axis=1, keepdims=True)
        if audio.ndim == 2:
            audio = audio.flatten()
        return audio.astype(np.float32)

    def process_chunk(self, audio: np.ndarray) -> float:
        if self._session is None:
            return 0.0
        audio = self._validate_input(audio)
        if len(audio) < 512:
            audio = np.pad(audio, (0, 512 - len(audio)))
        audio_2d = audio[:512].reshape(1, -1).astype(np.float32)
        input_data = np.concatenate([self._context, audio_2d], axis=1)
        self._context = audio_2d[:, -self._context_size:]

        ort_inputs = {
            self._input_name: input_data,
            self._sr_name: np.array([self.sample_rate], dtype=np.int64),
            self._state_name: self._state,
        }
        out = self._session.run(None, ort_inputs)
        speech_prob = float(out[0][0][0])
        self._state = out[1]

        return speech_prob

    def is_speech_segment(self, speech_prob: float) -> bool:
        self._frame_count += 1

        if speech_prob > self.threshold:
            self._speech_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1
            if self._is_speech and self._silence_frames > self.silence_frames:
                self._is_speech = False
                self._speech_frames = 0
            return False

        if (
            not self._is_speech
            and self._speech_frames > self.min_speech_frames
        ):
            self._is_speech = True
            self._speech_start_frame = self._frame_count
            return True

        return self._is_speech

    def is_ready(self) -> bool:
        return self._session is not None

    def reset(self):
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._context_size), dtype=np.float32)
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speech = False
        logger.debug("VAD state reset")
