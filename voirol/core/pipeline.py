import threading
import time
from enum import Enum
from typing import Callable

import numpy as np

from voirol.asr.engine import ASREngine
from voirol.asr.vosk_engine import VoskEngine
from voirol.asr.sensevoice_engine import SenseVoiceEngine
from voirol.audio.capture import AudioCapture
from voirol.audio.processor import preprocess
from voirol.audio.vad import SileroVAD
from voirol.command.actions import (
    black_screen,
    enter,
    esc,
    mute,
    next_page,
    open_browser,
    open_file_dialog,
    open_whiteboard,
    prev_page,
    space,
    white_screen,
)
from voirol.command.matcher import CommandMatcher
from voirol.command.registry import Command, CommandRegistry
from voirol.core.config import Config
from voirol.utils.i18n import t
from voirol.utils.logger import get_logger
from voirol.voice.enrollment import EnrollmentManager
from voirol.voice.verifier import SpeakerVerifier

logger = get_logger("core.pipeline")


class PipelineState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    VERIFYING = "verifying"
    PROCESSING = "processing"


class VoicePipeline:
    def __init__(self, config: Config):
        self.config = config
        self.state = PipelineState.IDLE
        self.muted = False
        self.ptt_active = False
        self._running = False
        self._thread: threading.Thread | None = None
        self._state_callbacks: list[Callable[[PipelineState], None]] = []
        self._command_callbacks: list[Callable[[str], None]] = []
        self._audio_buffer: list[np.ndarray] = []
        self._vad_buffer: list[float] = []
        self._in_speech = False
        self._ring_buffer: list[np.ndarray] = []

        sr = config.general["sample_rate"]
        block = config.general["block_size"]
        rb_seconds = self.config.voice.get("ring_buffer_seconds", 2.0)
        self._ring_buffer_max_frames = max(1, int(sr / block * rb_seconds))

        debug = config.debug
        self._verbose = debug.get("verbose", False)
        self._print_vad = debug.get("print_vad", False)
        self._log_asr_unverified = debug.get("log_asr_unverified", False)

        self.capture = AudioCapture(
            sample_rate=sr,
            block_size=block,
            device=config.general.get("input_device") or None,
        )

        vad_cfg = config.vad
        self.vad = SileroVAD(
            model_path="models/silero_vad.onnx",
            threshold=vad_cfg["threshold"],
            sample_rate=sr,
            min_speech_duration=vad_cfg["min_speech_duration"],
            silence_duration=vad_cfg["silence_duration"],
        )

        voice_cfg = config.voice
        self.verifier = SpeakerVerifier(
            threshold=voice_cfg["verification_threshold"],
            model_path=voice_cfg.get("model_path", "campplus-zh-en"),
        )
        self.enrollment = EnrollmentManager(
            enrollment_dir=voice_cfg["enrollment_dir"],
        )

        asr_cfg = config.asr
        engine_type = asr_cfg.get("engine", "vosk")
        if engine_type == "sensevoice":
            self.asr_engine: ASREngine = SenseVoiceEngine(
                model_dir=asr_cfg.get("sensevoice_model_path", "models/sensevoice"),
                num_threads=asr_cfg.get("sensevoice_num_threads", 2),
                language=asr_cfg.get("sensevoice_language", "zh"),
                use_itn=asr_cfg.get("sensevoice_use_itn", False),
            )
        elif engine_type == "baidu":
            from voirol.asr.baidu_engine import BaiduEngine
            self.asr_engine: ASREngine = BaiduEngine(
                api_key=asr_cfg["baidu_api_key"],
                secret_key=asr_cfg["baidu_secret_key"],
                language=asr_cfg.get("sensevoice_language", "zh"),
            )
        else:
            self.asr_engine: ASREngine = VoskEngine(
                model_path=asr_cfg["vosk_model_path"],
                language=asr_cfg["vosk_language"],
            )

        self._setup_commands()
        cmd_cfg = config.commands
        self.matcher = CommandMatcher(
            self._cmd_registry,
            mode=cmd_cfg["match_mode"],
            threshold=cmd_cfg["fuzzy_threshold"],
        )

        teacher_name = config.teacher.get("current_teacher", "")
        if teacher_name:
            profile = self.enrollment.get_profile(teacher_name)
            if profile:
                self.verifier.set_profile(profile)
                logger.info(f"Auto-loaded teacher: {teacher_name}")

    def _setup_commands(self):
        reg = CommandRegistry()

        reg.register(Command("next_page", ["下一页", "下一张", "下一页幻灯片", "下页"], "下一页", next_page))
        reg.register(Command("prev_page", ["上一页", "上一张", "上一页幻灯片", "上页"], "上一页", prev_page))
        reg.register(Command("black_screen", ["黑屏", "关屏幕", "关闭显示", "黑屏显示"], "黑屏", black_screen))
        reg.register(Command("white_screen", ["白屏", "白板", "白屏显示", "白板显示"], "白屏", white_screen))
        reg.register(Command("open_whiteboard", ["打开白板", "启动白板", "打开画板", "启动画板"], "打开白板", open_whiteboard))
        reg.register(Command("open_browser", ["打开浏览器", "启动浏览器", "打开网页", "启动网页"], "打开浏览器", open_browser))
        reg.register(Command("open_file", ["打开文件", "选择文件"], "打开文件", open_file_dialog))
        reg.register(Command("open_file", ["打开文件", "打开", "选择文件"], "打开文件", open_file_dialog))
        from voirol.command.actions import volume_up as _vu, volume_down as _vd, fullscreen as _fs

        reg.register(Command("volume_up", ["调高音量", "声音大点", "大声点", "加大音量", "增大音量", "音量加"], "调高音量", _vu))
        reg.register(Command("volume_down", ["调低音量", "声音小点", "小声点", "减小音量", "降低音量", "音量减"], "调低音量", _vd))
        reg.register(Command("mute", ["静音", "关闭声音", "无声", "安静"], "静音", mute))
        reg.register(Command("fullscreen", ["全屏", "全屏播放", "全屏显示"], "全屏", _fs))
        reg.register(Command("esc", ["退出", "取消", "返回", "退出全屏"], "退出", esc))
        reg.register(Command("space", ["暂停", "播放", "继续", "空格"], "暂停/播放", space))
        reg.register(Command("enter", ["确定", "确认", "回车"], "确定", enter))

        self._cmd_registry = reg

    def on_state_change(self, callback: Callable[[PipelineState], None]):
        self._state_callbacks.append(callback)

    def on_command(self, callback: Callable[[str], None]):
        self._command_callbacks.append(callback)

    def _set_state(self, state: PipelineState):
        self.state = state
        for cb in self._state_callbacks:
            try:
                cb(state)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def _process_audio(self, audio: np.ndarray):
        processed = preprocess(audio, self.config.general["sample_rate"])
        prob = self.vad.process_chunk(processed)
        self.vad.is_speech_segment(prob)

        if self.vad._is_speech:
            if not self._in_speech:
                self._in_speech = True
                self._speech_start_time = time.time()
                self._audio_buffer = list(self._ring_buffer)
                self._ring_buffer.clear()
                self._audio_buffer.append(processed.copy())
                self._set_state(PipelineState.LISTENING)
                if self._verbose:
                    print(t("vad.speech_start", n=len(self._audio_buffer) - 1))
            else:
                self._audio_buffer.append(processed.copy())
        else:
            if self._in_speech:
                self._in_speech = False
                duration = time.time() - self._speech_start_time
                if self._verbose:
                    print(t("vad.speech_end", duration=duration, n=len(self._audio_buffer)))
                self._set_state(PipelineState.VERIFYING)
                threading.Thread(
                    target=self._handle_speech_segment,
                    daemon=True,
                ).start()
            else:
                self._ring_buffer.append(processed.copy())
                if len(self._ring_buffer) > self._ring_buffer_max_frames:
                    self._ring_buffer.pop(0)

    def _handle_speech_segment(self):
        if not self._audio_buffer:
            self._set_state(PipelineState.IDLE)
            return

        full_audio = np.concatenate(self._audio_buffer)
        self._audio_buffer.clear()

        sr = self.config.general["sample_rate"]
        if len(full_audio) < sr * 0.3:
            if self._verbose:
                print(t("verify.too_short", duration=len(full_audio) / sr))
            self._set_state(PipelineState.IDLE)
            return

        if self._verbose:
            print(t("verify.running"))

        is_verified, sim = self.verifier.verify(full_audio, sr)

        threshold = self.config.voice.get("verification_threshold", 0.45)
        if self._verbose:
            status = t("verify.passed") if is_verified else t("verify.failed")
            print(t("verify.result", sim=sim, threshold=threshold, status=status))

        if not is_verified and not self._log_asr_unverified:
            if self._verbose:
                print(t("verify.skipping_asr"))
            self._set_state(PipelineState.IDLE)
            return

        self._set_state(PipelineState.PROCESSING)

        if self._verbose:
            print(t("asr.running"))

        text = self.asr_engine.transcribe(full_audio, sr)

        if self._verbose:
            print(t("asr.result", text=text))

        if not text:
            if self._verbose:
                print(t("asr.empty"))
            self._set_state(PipelineState.IDLE)
            return

        if not is_verified and self._log_asr_unverified:
            if self._verbose:
                print(t("cmd.unverified_print"))
            self._set_state(PipelineState.IDLE)
            return

        cmd = self.matcher.match(text)
        if cmd:
            if self._verbose:
                print(t("cmd.matched", cmd_id=cmd.id, description=cmd.description))
            try:
                cmd.action()
                for cb in self._command_callbacks:
                    try:
                        cb(cmd.id)
                    except Exception as e:
                        logger.error(f"Command callback error: {e}")
            except Exception as e:
                logger.error(f"Command execution failed: {e}")
        else:
            if self._verbose:
                print(t("cmd.no_match"))

        self._set_state(PipelineState.IDLE)

    def _processing_loop(self):
        while self._running:
            audio = self.capture.read_block(timeout=0.1)
            if audio is not None and not self.muted:
                self._process_audio(audio)

    def start(self):
        if self._running:
            return

        logger.info("Starting voice pipeline...")
        self.asr_engine.load()

        self.capture.start()
        self._running = True
        self._thread = threading.Thread(target=self._processing_loop, daemon=True)
        self._thread.start()
        self._set_state(PipelineState.IDLE)
        logger.info("Voice pipeline started")

    def stop(self):
        if not self._running:
            return

        logger.info("Stopping voice pipeline...")
        self._running = False
        self.capture.stop()
        self.asr_engine.unload()
        self.vad.reset()
        self._set_state(PipelineState.IDLE)
        logger.info("Voice pipeline stopped")

    def pause(self):
        if not self._running:
            return
        self.capture.stop()
        logger.info("Pipeline paused")

    def resume(self):
        if not self._running:
            return
        self.capture.start()
        logger.info("Pipeline resumed")

    def set_teacher(self, teacher_name: str):
        profile = self.enrollment.get_profile(teacher_name)
        if profile:
            self.verifier.set_profile(profile)
            self.config.teacher["current_teacher"] = teacher_name
            logger.info(f"Switched to teacher: {teacher_name}")
            return True
        logger.warning(f"Teacher not found: {teacher_name}")
        return False

    def _ptt_pressed(self):
        self.ptt_active = True
        self._audio_buffer = []
        self._in_speech = True
        self._speech_start_time = time.time()
        self._set_state(PipelineState.LISTENING)
        if self._verbose:
            print(t("ptt.pressed"))
        logger.debug("PTT: listening started")

    def _ptt_released(self):
        self.ptt_active = False
        self._in_speech = False
        duration = time.time() - self._speech_start_time
        if self._audio_buffer:
            if self._verbose:
                print(t("ptt.released", duration=duration))
            self._set_state(PipelineState.VERIFYING)
            threading.Thread(
                target=self._handle_speech_segment,
                daemon=True,
            ).start()
        else:
            if self._verbose:
                print(t("ptt.no_audio"))
            self._set_state(PipelineState.IDLE)
        logger.debug("PTT: listening ended")

    def setup_hotkeys(self, ptt_key: str = "ctrl+alt+v"):
        try:
            import keyboard as kb

            hotkey_parts = ptt_key.lower().split("+")
            if len(hotkey_parts) >= 2:
                mods = "+".join(hotkey_parts[:-1])
                key = hotkey_parts[-1]

                kb.add_hotkey(ptt_key, self._ptt_pressed, suppress=True)
                kb.on_release_key(
                    key,
                    lambda e: self._ptt_released()
                    if self.ptt_active
                    else None,
                )
                logger.info(f"PTT hotkey registered: {ptt_key}")
            else:
                logger.warning(f"Invalid hotkey format: {ptt_key}")
        except ImportError:
            logger.warning(
                "keyboard module not available, PTT disabled. "
                "Install with: pip install keyboard"
            )
        except Exception as e:
            logger.error(f"Failed to register PTT hotkey: {e}")
