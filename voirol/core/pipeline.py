import concurrent.futures
import os
import subprocess
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Callable

import numpy as np

from voirol.ai.matcher import AIMatcher
from voirol.ai.openai_engine import OpenAIEngine
from voirol.asr.engine import ASREngine
from voirol.asr.sensevoice_engine import SenseVoiceEngine
from voirol.audio.capture import AudioCapture
from voirol.audio.processor import preprocess
from voirol.audio.vad import SileroVAD
from voirol.agent.engine import AgentEngine, set_current_engine
from voirol.agent.screen import ScreenAnalyzer
from voirol.agent.skill_registry import SkillRegistry, Skill
from voirol.agent.mouse import (
    skill_click, skill_double_click, skill_right_click,
    skill_drag, skill_scroll, skill_move_mouse,
)
from voirol.agent.keyboard import (
    skill_type_text, skill_press_key, skill_hotkey, skill_press_and_release,
)
from voirol.agent.file_ops import (
    skill_open_app, skill_run_command, skill_read_file, skill_write_file,
    skill_find_file,
)
from voirol.tts.moss_api import MossApiEngine
from voirol.command.actions import (
    agent_execute,
    black_screen,
    enter,
    esc,
    mute,
    next_page,
    open_file_action,
    open_router,
    open_url,
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
        self._audio_level_callbacks: list[Callable[[float], None]] = []
        self._asr_callbacks: list[Callable[[str], None]] = []
        self._action_callbacks: list[Callable[[str], None]] = []
        self._callback_lock = threading.Lock()
        self._audio_buffer: list[np.ndarray] = []
        self._audio_lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self._vad_buffer: list[float] = []
        self._in_speech = False
        self._speech_lock = threading.Lock()
        self._ring_buffer: list[np.ndarray] = []
        self._rms_peak = 0.01
        self._hotkey_handle = None
        self._ai_matcher: AIMatcher | None = None
        self._file_navigator = None
        self._agent_engine: AgentEngine | None = None
        self._tts_engine: MossApiEngine | None = None
        self._tts_process: subprocess.Popen | None = None

        self._init_audio(config)
        self._init_voice(config)
        self._init_asr(config)
        self._setup_commands()
        self._init_matcher(config)
        self._init_ai(config)
        self._init_tts(config)
        self._init_bindings(config)

    def _init_audio(self, config: Config):
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
        self._vad_ready = self.vad.is_ready()
        if not self._vad_ready:
            logger.warning("Silero VAD model not found. Voice detection disabled.")
        self._asr_ready = False

    def _init_voice(self, config: Config):
        voice_cfg = config.voice
        self.verifier = SpeakerVerifier(
            threshold=voice_cfg["verification_threshold"],
            model_path=voice_cfg.get("model_path", "campplus-zh-en"),
        )
        self.enrollment = EnrollmentManager(
            enrollment_dir=voice_cfg["enrollment_dir"],
        )

    def _init_asr(self, config: Config):
        asr_cfg = config.asr
        engine_type = asr_cfg.get("engine", "sensevoice")
        if engine_type == "baidu":
            from voirol.asr.baidu_engine import BaiduEngine
            self.asr_engine: ASREngine = BaiduEngine(
                api_key=asr_cfg["baidu_api_key"],
                secret_key=asr_cfg["baidu_secret_key"],
                language=asr_cfg.get("sensevoice_language", "zh"),
            )
        elif engine_type == "azure":
            from voirol.asr.azure_engine import AzureEngine
            self.asr_engine: ASREngine = AzureEngine(
                subscription_key=asr_cfg.get("azure_subscription_key", ""),
                region=asr_cfg.get("azure_region", ""),
                language=asr_cfg.get("sensevoice_language", "zh"),
            )
        elif engine_type == "tencent":
            from voirol.asr.tencent_engine import TencentEngine
            self.asr_engine: ASREngine = TencentEngine(
                secret_id=asr_cfg.get("tencent_secret_id", ""),
                secret_key=asr_cfg.get("tencent_secret_key", ""),
                language=asr_cfg.get("sensevoice_language", "zh"),
            )
        else:
            self.asr_engine: ASREngine = SenseVoiceEngine(
                model_dir=asr_cfg.get("sensevoice_model_path", "models/sensevoice"),
                num_threads=asr_cfg.get("sensevoice_num_threads", 2),
                language=asr_cfg.get("sensevoice_language", "zh"),
                use_itn=asr_cfg.get("sensevoice_use_itn", False),
            )

    def _init_matcher(self, config: Config):
        cmd_cfg = config.commands
        self.matcher = CommandMatcher(
            self._cmd_registry,
            mode=cmd_cfg["match_mode"],
            threshold=cmd_cfg["fuzzy_threshold"],
        )

    def _init_ai(self, config: Config):
        ai_cfg = config.ai
        agent_cfg = config.agent
        ai_enabled = ai_cfg.get("enabled") and ai_cfg.get("api_key")

        if not ai_enabled:
            logger.info("AI services disabled (no api_key)")
            return

        llm_engine = OpenAIEngine(
            api_url=ai_cfg.get("api_url", "https://api.deepseek.com/v1"),
            api_key=ai_cfg.get("api_key", ""),
            model=ai_cfg.get("model", "deepseek-chat"),
        )

        self._ai_matcher = AIMatcher(
            engine=llm_engine,
            registry=self._cmd_registry,
            system_prompt=ai_cfg.get("system_prompt", ""),
            temperature=ai_cfg.get("temperature", 0.1),
            timeout=ai_cfg.get("timeout", 10),
        )
        logger.info("AI command matcher enabled")

        from voirol.command.file_navigator import FileNavigator
        from voirol.command.actions import set_file_navigator, set_ai_router_engine
        self._file_navigator = FileNavigator(
            engine=llm_engine,
            max_depth=config.file.get("ai_search_depth", 5),
            status_callback=self._on_navigator_status,
        )
        set_file_navigator(self._file_navigator)
        set_ai_router_engine(llm_engine)
        logger.info("File navigator enabled")

        from voirol.agent.file_ops import set_shared_engine
        set_shared_engine(llm_engine, self._file_navigator, config.file.get("search_dirs"))

        if not agent_cfg.get("enabled"):
            logger.info("Agent engine disabled")
            return

        try:
            self._agent_engine = AgentEngine(
                screen_analyzer=ScreenAnalyzer(
                    ocr_lang=agent_cfg.get("ocr_lang", "chi_sim+eng"),
                ),
                skill_registry=self._build_agent_skills(),
                llm_engine=llm_engine,
                max_steps=agent_cfg.get("max_steps", 30),
                temperature=agent_cfg.get("temperature", 0.1),
                timeout=agent_cfg.get("timeout", 15),
            )
            set_current_engine(self._agent_engine)
            logger.info("Agent engine enabled")
            self._agent_engine.on_step(lambda skill, reasoning, result: (
                [cb(f"[agent] {skill}: {result[:80]}") for cb in self._action_callbacks]
            ))
        except Exception as e:
            logger.warning(f"Failed to initialize agent engine: {e}")
            self._agent_engine = None

    def _init_tts(self, config: Config):
        tts_cfg = config.tts
        if not tts_cfg.get("enabled"):
            return
        try:
            self._tts_engine = MossApiEngine(
                host=tts_cfg.get("host", "127.0.0.1"),
                port=tts_cfg.get("port", 8080),
                voice=tts_cfg.get("voice", "Xiaoyu"),
            )
            logger.info("TTS engine initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize TTS engine: {e}")
            self._tts_engine = None

    def _init_bindings(self, config: Config):
        from voirol.command.actions import set_default_browser, set_search_engine, set_file_search_dirs, set_agent_engine
        if self._agent_engine is not None:
            set_agent_engine(self._agent_engine)
        browser_cfg = config.browser
        set_default_browser(browser_cfg.get("default", "edge"))
        se = browser_cfg.get("search_engine", "")
        if se:
            set_search_engine(se)

        file_cfg = config.file
        dirs = file_cfg.get("search_dirs")
        if dirs:
            set_file_search_dirs(dirs)

        teacher_name = config.teacher.get("current_teacher", "")
        if teacher_name:
            profile = self.enrollment.get_profile(teacher_name)
            if profile:
                self.verifier.set_profile(profile)
                logger.info(f"Auto-loaded teacher: {teacher_name}")

    @property
    def is_running(self) -> bool:
        return self._running

    def _setup_commands(self):
        reg = CommandRegistry()

        reg.register(Command("next_page", ["下一页", "下一张", "下一页幻灯片", "下页"], t("cmd.desc.next_page"), next_page))
        reg.register(Command("prev_page", ["上一页", "上一张", "上一页幻灯片", "上页"], t("cmd.desc.prev_page"), prev_page))
        reg.register(Command("black_screen", ["黑屏", "关屏幕", "关闭显示", "黑屏显示"], t("cmd.desc.black_screen"), black_screen))
        reg.register(Command("white_screen", ["白屏", "白板", "白屏显示", "白板显示"], t("cmd.desc.white_screen"), white_screen))
        reg.register(Command("open_whiteboard", ["打开白板", "启动白板", "打开画板", "启动画板"], t("cmd.desc.open_whiteboard"), open_whiteboard))
        reg.register(Command("open_browser", ["打开浏览器", "启动浏览器", "打开网页", "启动网页", "打开网址", "访问", "进入"], t("cmd.desc.open_browser"), open_url, capture_param=True))
        reg.register(Command("open_file", ["打开文件", "选择文件"], t("cmd.desc.open_file"), open_file_action, capture_param=True))
        reg.register(Command("open", ["打开"], t("cmd.desc.open"), open_router, capture_param=True))
        from voirol.command.actions import volume_up as _vu, volume_down as _vd, fullscreen as _fs, agent_execute

        reg.register(Command("volume_up", ["调高音量", "声音大点", "大声点", "加大音量", "增大音量", "音量加"], t("cmd.desc.volume_up"), _vu))
        reg.register(Command("volume_down", ["调低音量", "声音小点", "小声点", "减小音量", "降低音量", "音量减"], t("cmd.desc.volume_down"), _vd))
        reg.register(Command("mute", ["静音", "关闭声音", "无声", "安静"], t("cmd.desc.mute"), mute))
        reg.register(Command("fullscreen", ["全屏", "全屏播放", "全屏显示"], t("cmd.desc.fullscreen"), _fs))
        reg.register(Command("esc", ["退出", "取消", "返回", "退出全屏"], t("cmd.desc.esc"), esc))
        reg.register(Command("space", ["暂停", "播放", "继续", "空格"], t("cmd.desc.space"), space))
        reg.register(Command("enter", ["确定", "确认", "回车"], t("cmd.desc.enter"), enter))
        reg.register(Command("agent", ["电脑操作", "操作电脑", "帮我打开", "帮我找", "帮我搜索", "帮我", "桌面操作", "screen"], t("cmd.desc.agent"), agent_execute, capture_param=True))

        self._cmd_registry = reg

    def _build_agent_skills(self) -> SkillRegistry:
        reg = SkillRegistry()
        reg.register(Skill("click_element", "Click a UI element by its element_id from the screen observation", {"type": "object", "properties": {"element_id": {"type": "integer"}}, "required": ["element_id"]}, skill_click, resolve_element=True))
        reg.register(Skill("double_click_element", "Double-click a UI element by its element_id (use for desktop icons)", {"type": "object", "properties": {"element_id": {"type": "integer"}}, "required": ["element_id"]}, skill_double_click, resolve_element=True))
        reg.register(Skill("click", "Click at specific x,y coordinates", {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"}}, "required": ["x", "y"]}, skill_click))
        reg.register(Skill("double_click", "Double click at coordinates or element", {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}, skill_double_click))
        reg.register(Skill("right_click", "Right click at coordinates", {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}, skill_right_click))
        reg.register(Skill("drag", "Drag from one point to another", {"type": "object", "properties": {"from_x": {"type": "integer"}, "from_y": {"type": "integer"}, "to_x": {"type": "integer"}, "to_y": {"type": "integer"}, "duration": {"type": "number", "default": 0.5}}, "required": ["from_x", "from_y", "to_x", "to_y"]}, skill_drag))
        reg.register(Skill("scroll", "Scroll the mouse wheel", {"type": "object", "properties": {"clicks": {"type": "integer"}, "x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["clicks"]}, skill_scroll))
        reg.register(Skill("move_mouse", "Move mouse to coordinates", {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "duration": {"type": "number", "default": 0.3}}, "required": ["x", "y"]}, skill_move_mouse))
        reg.register(Skill("type_text", "Type text at the current focus", {"type": "object", "properties": {"text": {"type": "string"}, "interval": {"type": "number", "default": 0.05}}, "required": ["text"]}, skill_type_text))
        reg.register(Skill("press_key", "Press a single key (or key combo with +)", {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}, skill_press_key))
        reg.register(Skill("hotkey", "Press a hotkey combination", {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}}, "required": ["keys"]}, skill_hotkey))
        reg.register(Skill("press_and_release", "Press and release a sequence of modifier keys", {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}}, "required": ["keys"]}, skill_press_and_release))
        reg.register(Skill("open_app", "Open an application or file", {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}, skill_open_app))
        reg.register(Skill("run_command", "Execute a shell command", {"type": "object", "properties": {"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer", "default": 30}}, "required": ["command"]}, skill_run_command))
        reg.register(Skill("read_file", "Read a file from disk", {"type": "object", "properties": {"path": {"type": "string"}, "max_chars": {"type": "integer", "default": 5000}}, "required": ["path"]}, skill_read_file))
        reg.register(Skill("write_file", "Write content to a file", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}, skill_write_file))
        reg.register(Skill("find_file", "Search for a file on the filesystem by name or description", {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}, skill_find_file))
        reg.register(Skill("done", "Signal that the task is complete", {"type": "object", "properties": {"result": {"type": "string"}}, "required": ["result"]}, lambda p: p.get("result", "")))
        reg.register(Skill("ask_user", "Ask the user a question when the instruction is ambiguous", {"type": "object", "properties": {"question": {"type": "string", "description": "The question to ask the user"}}, "required": ["question"]}, lambda p: ""))

        def _skill_open_url(p: dict) -> str:
            from voirol.command.actions import open_url as _open_url
            result = _open_url(p["url"])
            return f"Opened URL: {p['url']}"

        def _skill_minimize_all(p: dict) -> str:
            import pyautogui
            pyautogui.hotkey("win", "d")
            return "Minimized all windows (Win+D)"

        reg.register(Skill("open_url", "Open a URL in the default browser", {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}, _skill_open_url))
        reg.register(Skill("minimize_all", "Minimize all windows to show desktop (Win+D)", {"type": "object", "properties": {}, "required": []}, _skill_minimize_all))
        return reg

    @property
    def agent_engine(self):
        return self._agent_engine

    def _on_navigator_status(self, text: str):
        for cb in self._command_callbacks:
            try:
                cb(f"nav:{text}")
            except Exception:
                pass
        for cb in self._action_callbacks:
            try:
                cb(text)
            except Exception:
                pass

    @property
    def tts_engine(self) -> MossApiEngine | None:
        return self._tts_engine

    def speak(self, text: str, wait: bool = False) -> None:
        if self._tts_engine is None or not self._tts_engine.is_ready():
            return
        try:
            for cb in self._action_callbacks:
                try:
                    cb(f"[tts] 🔊 {text[:60]}")
                except Exception:
                    pass
            if wait:
                self._tts_engine.synthesize(text)
            else:
                self._tts_engine.synthesize_async(text)
        except Exception as e:
            logger.warning(f"TTS speak failed: {e}")

    def _launch_tts_server(self) -> subprocess.Popen | None:
        cfg = self.config.tts
        model_path = cfg.get("model_path", "models/moss-tts-nano")
        tok_path = cfg.get("audio_tokenizer_path", "models/moss-audio-tokenizer-nano")

        if not os.path.isdir(model_path) or not os.path.isdir(tok_path):
            logger.warning(f"TTS model/tokenizer directory not found: {model_path}, {tok_path}")
            return None

        import shutil
        runtime_py = os.path.join("runtime", "python", "python.exe")
        if os.path.exists(runtime_py):
            full_cmd = [os.path.abspath(runtime_py), "-m", "moss_tts_nano.serve"]
        else:
            cmd = shutil.which("moss-tts-nano")
            if cmd:
                full_cmd = [cmd, "serve"]
            else:
                full_cmd = [sys.executable, "-m", "moss_tts_nano.serve"]

        full_cmd += [
            "--port", str(cfg.get("port", 8080)),
            "--checkpoint", model_path,
            "--audio-tokenizer-path", tok_path,
            "--device", "cpu",
        ]
        proc = subprocess.Popen(
            full_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.info(f"TTS server started: {' '.join(full_cmd)}")
        return proc

    def _wait_for_tts_ready(self, port: int, timeout: int = 60) -> bool:
        import requests
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = requests.get(f"http://127.0.0.1:{port}/api/warmup-status", timeout=2)
                if r.json().get("state") == "ready":
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False

    def _wait_tts_background(self, port: int, timeout: int):
        if self._wait_for_tts_ready(port, timeout):
            logger.info("TTS server ready")
            try:
                self._tts_engine.load()
            except Exception as e:
                logger.warning(f"TTS engine load failed: {e}")
        else:
            logger.warning("TTS server startup timed out")
            self._tts_engine = None

    def _stop_tts_server(self) -> None:
        if self._tts_process is not None:
            try:
                self._tts_process.terminate()
                self._tts_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    self._tts_process.kill()
                    self._tts_process.wait(timeout=5)
                except Exception as e:
                    logger.warning(f"Failed to kill TTS process: {e}")
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.warning(f"Error stopping TTS server: {e}")
            self._tts_process = None
            logger.info("TTS server stopped")

    def on_state_change(self, callback: Callable[[PipelineState], None]):
        with self._callback_lock:
            self._state_callbacks.append(callback)

    def on_command(self, callback: Callable[[str], None]):
        with self._callback_lock:
            self._command_callbacks.append(callback)

    def on_audio_level(self, callback: Callable[[float], None]):
        with self._callback_lock:
            self._audio_level_callbacks.append(callback)

    def on_asr_text(self, callback: Callable[[str], None]):
        with self._callback_lock:
            self._asr_callbacks.append(callback)

    def on_action(self, callback: Callable[[str], None]):
        with self._callback_lock:
            self._action_callbacks.append(callback)

    def _set_state(self, state: PipelineState):
        if not self._running:
            return
        self.state = state
        with self._callback_lock:
            cbs = list(self._state_callbacks)
        for cb in cbs:
            try:
                cb(state)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    def _emit_audio_level(self, chunk: np.ndarray):
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        self._rms_peak = max(self._rms_peak * 0.999, rms)
        noise_floor = 0.02
        if rms < noise_floor:
            level = 0.0
        else:
            level = min(1.0, (rms - noise_floor) / (self._rms_peak - noise_floor + 1e-8))
        with self._callback_lock:
            cbs = list(self._audio_level_callbacks)
        for cb in cbs:
            try:
                cb(level)
            except Exception as e:
                logger.error(f"Audio level callback error: {e}")

    def _process_audio(self, audio: np.ndarray):
        if not self._vad_ready:
            return
        processed = preprocess(audio, self.config.general["sample_rate"])
        prob = self.vad.process_chunk(processed)
        self.vad.is_speech_segment(prob)

        with self._speech_lock:
            in_speech = self._in_speech
            speech_start = self.vad._is_speech

        if self.vad._is_speech:
            if not in_speech:
                with self._speech_lock:
                    self._in_speech = True
                self._speech_start_time = time.time()
                with self._audio_lock:
                    self._audio_buffer = list(self._ring_buffer)
                    self._ring_buffer.clear()
                    self._audio_buffer.append(processed.copy())
                    prepend_n = len(self._audio_buffer) - 1
                self._set_state(PipelineState.LISTENING)
                self._emit_audio_level(processed)
                if self._verbose:
                    logger.debug(t("vad.speech_start", n=prepend_n))
            else:
                with self._audio_lock:
                    self._audio_buffer.append(processed.copy())
                self._emit_audio_level(processed)

                if self._check_utterance_timeout():
                    with self._speech_lock:
                        self._in_speech = False
                    self._set_state(PipelineState.VERIFYING)
                    self._executor.submit(self._handle_speech_segment)
        else:
            if in_speech:
                if self.ptt_active:
                    return
                with self._speech_lock:
                    self._in_speech = False
                duration = time.time() - self._speech_start_time
                if self._verbose:
                    logger.debug(t("vad.speech_end", duration=duration, n=len(self._audio_buffer)))
                self._set_state(PipelineState.VERIFYING)
                self._executor.submit(self._handle_speech_segment)
            else:
                self._ring_buffer.append(processed.copy())
                if len(self._ring_buffer) > self._ring_buffer_max_frames:
                    self._ring_buffer.pop(0)

    def _check_utterance_timeout(self) -> bool:
        max_sec = self.config.voice.get("max_utterance_seconds", 15)
        return time.time() - self._speech_start_time > max_sec

    def _handle_speech_segment(self):
        with self._audio_lock:
            if not self._audio_buffer:
                self._set_state(PipelineState.IDLE)
                return
            full_audio = np.concatenate(self._audio_buffer)
            self._audio_buffer.clear()

        sr = self.config.general["sample_rate"]
        if len(full_audio) < sr * 0.3:
            if self._verbose:
                logger.debug(t("verify.too_short", duration=len(full_audio) / sr))
            self._set_state(PipelineState.IDLE)
            return

        text = self._verify_and_transcribe(full_audio, sr)
        if text is None:
            return

        if self._try_agent_await(text):
            return

        self._match_and_dispatch(text)
        self._set_state(PipelineState.IDLE)

    def _verify_and_transcribe(self, full_audio: np.ndarray, sr: int) -> str | None:
        if self._verbose:
            logger.debug(t("verify.running"))

        is_verified, sim = self.verifier.verify(full_audio, sr)

        threshold = self.config.voice.get("verification_threshold", 0.45)
        if self._verbose:
            status = t("verify.passed") if is_verified else t("verify.failed")
            logger.debug(t("verify.result", sim=sim, threshold=threshold, status=status))

        if not is_verified and not self._log_asr_unverified:
            if self._verbose:
                logger.debug(t("verify.skipping_asr"))
            self._set_state(PipelineState.IDLE)
            return None

        self._set_state(PipelineState.PROCESSING)

        if not self._asr_ready:
            if self._verbose:
                logger.debug(t("asr.not_ready"))
            self._set_state(PipelineState.IDLE)
            return None

        if self._verbose:
            logger.debug(t("asr.running"))

        text = self.asr_engine.transcribe(full_audio, sr)

        if text:
            with self._callback_lock:
                cbs = list(self._asr_callbacks)
            for cb in cbs:
                try:
                    cb(text)
                except Exception as e:
                    logger.error(f"ASR callback error: {e}")

        if self._verbose:
            logger.debug(t("asr.result", text=text))

        if not text:
            if self._verbose:
                logger.debug(t("asr.empty"))
            self._set_state(PipelineState.IDLE)
            return None

        if not is_verified and self._log_asr_unverified:
            if self._verbose:
                logger.debug(t("cmd.unverified_print"))
            self._set_state(PipelineState.IDLE)
            return None

        return text

    def _try_agent_await(self, text: str) -> bool:
        if not self._agent_engine or not self._agent_engine.awaiting_answer:
            return False

        try:
            result = agent_execute(text)
            if isinstance(result, str) and result.startswith("[ASK_USER]"):
                question = result[len("[ASK_USER] "):]
                with self._callback_lock:
                    cbs = list(self._action_callbacks)
                for cb in cbs:
                    try:
                        cb(f"[询问] {question}")
                    except Exception as e:
                        logger.error(f"Action callback error: {e}")
                self.speak(question)
        except Exception as e:
            logger.error(f"Agent resume failed: {e}")
        self._set_state(PipelineState.IDLE)
        return True

    def _match_and_dispatch(self, text: str):
        cmd, param = self.matcher.match_with_param(text)
        if cmd is None and self._ai_matcher is not None:
            ai_cmd = self._ai_matcher.match(text)
            if ai_cmd is not None:
                cmd = ai_cmd
                param = text if cmd.capture_param else None
        if cmd:
            self._execute_command(cmd, param, text)
        else:
            self._fallback_agent(text)

    def _execute_command(self, cmd, param, text: str):
        if self._verbose:
            logger.debug(t("cmd.matched", cmd_id=cmd.id, description=cmd.description))
        desc = cmd.description
        if cmd.capture_param and param:
            desc = f"{desc}: {param}"
        with self._callback_lock:
            cbs_act = list(self._action_callbacks)
            cbs_cmd = list(self._command_callbacks)
        for cb in cbs_act:
            try:
                cb(f"→ {desc}")
            except Exception as e:
                logger.error(f"Action callback error: {e}")
        for cb in cbs_cmd:
            try:
                cb(f"cmd:{desc}")
            except Exception as e:
                logger.error(f"Command callback error: {e}")
        try:
            ask_user_result = None
            if cmd.capture_param:
                if cmd.id == "agent":
                    ask_user_result = cmd.action(text)
                else:
                    cmd.action(param or "")
            else:
                cmd.action()
            if isinstance(ask_user_result, str) and ask_user_result.startswith("[ASK_USER]"):
                question = ask_user_result[len("[ASK_USER] "):]
                for cb in cbs_act:
                    try:
                        cb(f"[询问] {question}")
                    except Exception as e:
                        logger.error(f"Action callback error: {e}")
                self.speak(question)
            for cb in cbs_cmd:
                try:
                    cb(cmd.id)
                except Exception as e:
                    logger.error(f"Command callback error: {e}")
        except Exception as e:
            logger.error(f"Command execution failed: {e}")

    def _fallback_agent(self, text: str):
        if self._verbose:
            logger.debug(t("cmd.no_match"))
        if not self._agent_engine:
            return
        try:
            result = agent_execute(text)
            with self._callback_lock:
                cbs = list(self._action_callbacks)
            for cb in cbs:
                try:
                    cb(f"[agent] {text}")
                except Exception as e:
                    logger.error(f"Action callback error: {e}")
        except Exception as e:
            logger.error(f"Agent fallback failed: {e}")

    def _processing_loop(self):
        while self._running:
            audio = self.capture.read_block(timeout=0.1)
            if audio is not None and not self.muted:
                self._process_audio(audio)

    def start(self):
        if self._running:
            return

        logger.info("Starting voice pipeline...")
        try:
            self.asr_engine.load()
            self._asr_ready = True
        except Exception as e:
            logger.warning(f"ASR engine failed to load: {e}. Voice commands disabled.")
            self._asr_ready = False

        if self._tts_engine is not None:
            try:
                proc = self._launch_tts_server()
                if proc is None:
                    logger.warning("TTS data missing, disabling TTS")
                    self._tts_engine = None
                else:
                    self._tts_process = proc
                    port = self.config.tts.get("port", 8080)
                    timeout = self.config.tts.get("server_timeout", 60)
                    threading.Thread(
                        target=self._wait_tts_background,
                        args=(port, timeout),
                        daemon=True,
                    ).start()
            except Exception as e:
                logger.warning(f"Failed to start TTS server: {e}")
                self._tts_engine = None

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
        self._executor.shutdown(wait=False)

        try:
            import keyboard as kb
            kb.unhook_all()
        except Exception:
            pass
        self._hotkey_handle = None

        self.capture.stop()
        self.asr_engine.unload()
        if self._tts_engine is not None:
            try:
                self._tts_engine.unload()
            except Exception:
                pass
        self._stop_tts_server()
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
        with self._audio_lock:
            self._audio_buffer = []
        with self._speech_lock:
            self._in_speech = True
        self._speech_start_time = time.time()
        self._set_state(PipelineState.LISTENING)
        if self._verbose:
            logger.debug(t("ptt.pressed"))
        logger.debug("PTT: listening started")

    def _ptt_released(self):
        with self._audio_lock:
            self.ptt_active = False
            has_audio = bool(self._audio_buffer)
        with self._speech_lock:
            self._in_speech = False
        duration = time.time() - self._speech_start_time
        if has_audio:
            if self._verbose:
                logger.debug(t("ptt.released", duration=duration))
            self._set_state(PipelineState.VERIFYING)
            self._executor.submit(self._handle_speech_segment)
        else:
            if self._verbose:
                logger.debug(t("ptt.no_audio"))
            self._set_state(PipelineState.IDLE)
        logger.debug("PTT: listening ended")

    def setup_hotkeys(self, ptt_key: str = "ctrl+alt+v"):
        try:
            import keyboard as kb

            hotkey_parts = ptt_key.lower().split("+")
            if len(hotkey_parts) >= 2:
                mods = "+".join(hotkey_parts[:-1])
                key = hotkey_parts[-1]

                self._hotkey_handle = kb.add_hotkey(ptt_key, self._ptt_pressed, suppress=True)
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
