import os
from dataclasses import dataclass, field
from typing import Any

import toml

from voirol.utils.i18n import set_language
from voirol.utils.logger import get_logger

logger = get_logger("core.config")

DEFAULT_CONFIG_PATH = "config.toml"


@dataclass
class Config:
    general: dict = field(default_factory=lambda: {
        "language": "zh-CN",
        "sample_rate": 16000,
        "block_size": 1024,
        "input_device": -1,
    })
    vad: dict = field(default_factory=lambda: {
        "type": "silero",
        "threshold": 0.5,
        "min_speech_duration": 0.5,
        "silence_duration": 0.8,
    })
    voice: dict = field(default_factory=lambda: {
        "model_path": "campplus-zh-en",
        "verification_threshold": 0.45,
        "enrollment_utterances": 5,
        "enrollment_dir": "data/enrollments",
        "ring_buffer_seconds": 2.0,
        "max_utterance_seconds": 15,
    })
    asr: dict = field(default_factory=lambda: {
        "engine": "vosk",
        "vosk_model_path": "models/vosk_zh",
        "vosk_language": "zh-cn",
        "sensevoice_model_path": "models/sensevoice",
        "sensevoice_num_threads": 2,
        "sensevoice_language": "zh",
        "sensevoice_use_itn": False,
        "baidu_app_id": "",
        "baidu_api_key": "",
        "baidu_secret_key": "",
        "azure_subscription_key": "",
        "azure_region": "",
        "tencent_secret_id": "",
        "tencent_secret_key": "",
    })
    commands: dict = field(default_factory=lambda: {
        "match_mode": "fuzzy",
        "fuzzy_threshold": 0.8,
    })
    hotkey: dict = field(default_factory=lambda: {
        "push_to_talk": "ctrl+alt+v",
        "toggle_mute": "ctrl+alt+m",
        "open_settings": "ctrl+alt+s",
    })
    ui: dict = field(default_factory=lambda: {
        "font_size": 13,
        "border_radius": 5,
        "theme": "system",
    })
    teacher: dict = field(default_factory=lambda: {
        "current_teacher": "",
    })
    debug: dict = field(default_factory=lambda: {
        "verbose": False,
        "print_vad": False,
        "log_asr_unverified": False,
    })
    download: dict = field(default_factory=lambda: {
        "mirror_url": "",
    })
    ai: dict = field(default_factory=lambda: {
        "enabled": False,
        "provider": "openai",
        "api_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat",
        "temperature": 0.1,
        "timeout": 10,
        "system_prompt": "",
    })
    browser: dict = field(default_factory=lambda: {
        "default": "edge",
        "search_engine": "https://www.baidu.com/s?wd={}",
    })
    file: dict = field(default_factory=lambda: {
        "search_dirs": ["~/Desktop", "~/Documents", "~/Downloads"],
        "ai_search_depth": 5,
    })
    logging: dict = field(default_factory=lambda: {
        "level": "INFO",
        "file": "",
    })


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Config:
    cfg = Config()
    if not os.path.exists(path):
        logger.info(f"Config file not found, using defaults: {path}")
        save_config(cfg, path)
        return cfg

    try:
        data = toml.load(path)
        for section in cfg.__annotations__:
            if section in data:
                getattr(cfg, section).update(data[section])
        logger.info(f"Config loaded from {path}")
    except Exception as e:
        logger.warning(f"Failed to load config: {e}, using defaults")

    set_language(cfg.general.get("language", "en"))
    return cfg


def save_config(cfg: Config, path: str = DEFAULT_CONFIG_PATH):
    data = {}
    for section in cfg.__annotations__:
        data[section] = getattr(cfg, section)

    try:
        with open(path, "w", encoding="utf-8") as f:
            toml.dump(data, f)
        logger.info(f"Config saved to {path}")
    except Exception as e:
        logger.error(f"Failed to save config: {e}")


def get_nested(cfg: Config, key_path: str, default: Any = None) -> Any:
    parts = key_path.split(".")
    obj = cfg
    for part in parts:
        if isinstance(obj, Config):
            obj = getattr(obj, part, {})
        elif isinstance(obj, dict):
            obj = obj.get(part, {})
        else:
            return default
    return obj if obj != {} else default


def set_nested(cfg: Config, key_path: str, value: Any):
    parts = key_path.split(".")
    if len(parts) == 1:
        setattr(cfg, parts[0], value)
    elif len(parts) == 2:
        section = getattr(cfg, parts[0], {})
        if isinstance(section, dict):
            section[parts[1]] = value
