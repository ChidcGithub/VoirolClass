import queue
import threading
from typing import Callable

import numpy as np
import sounddevice as sd

from voirol.utils.logger import get_logger

logger = get_logger("audio.capture")


class AudioCapture:
    def __init__(
        self,
        sample_rate: int = 16000,
        block_size: int = 512,
        device: int | None = None,
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.device = device
        self._queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)
        self._stream: sd.InputStream | None = None
        self._running = False
        self._find_valid_device()

    def _find_valid_device(self):
        if self.device is not None and self.device >= 0:
            return

        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                try:
                    name = str(dev["name"])
                except Exception:
                    continue
                if dev["max_input_channels"] > 0:
                    try:
                        sd.query_devices(i)
                        self.device = i
                        logger.info(f"Auto-selected input device: {i} ({name})")
                        return
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Could not enumerate audio devices: {e}")

        logger.warning("No input device found. Run with a microphone connected.")
        self.device = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        if status:
            logger.warning(f"Audio input status: {status}")
        try:
            self._queue.put_nowait(indata.copy())
        except queue.Full:
            pass

    def start(self):
        if self._running:
            return

        if self.device is None:
            raise RuntimeError(
                "No microphone detected. Please connect a microphone "
                "and restart VoirolClass."
            )

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                device=self.device,
                channels=1,
                dtype=np.float32,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._running = True
            logger.info(
                f"Audio capture started (device={self.device}, "
                f"rate={self.sample_rate})"
            )
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            raise

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._running = False
        logger.info("Audio capture stopped")

    def read_block(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def read_blocks(self, n: int, timeout: float = 2.0) -> np.ndarray | None:
        chunks = []
        for _ in range(n):
            chunk = self.read_block(timeout=timeout / n)
            if chunk is None:
                break
            chunks.append(chunk)
        if not chunks:
            return None
        return np.concatenate(chunks, axis=0)
