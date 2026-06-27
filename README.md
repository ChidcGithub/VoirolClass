# VoirolClass

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey)](https://www.microsoft.com/windows)
[![Version](https://img.shields.io/badge/version-0.0.1--beta-orange)]()

> [中文文档](README_zh.md)

A voice-controlled classroom assistant for teachers. Speak naturally to control slides, screens, volume, and applications — hands-free.

> **MVP** — built for classroom use on Windows (4 GB RAM, low-end CPU). Supports offline ASR via SenseVoice or Vosk, and speaker verification to ensure only the enrolled teacher's voice triggers commands.

## Features

- **Voice Activity Detection** — Silero VAD ONNX with configurable sensitivity, speech/silence duration, and a ring buffer that preserves ~1 s of audio history to avoid cutting off sentence starts
- **Dual ASR Engines** — SenseVoiceSmall (pure ONNX Runtime, primary) or Vosk-Kaldi (fallback), both running fully offline
- **Speaker Verification** — CAM++ embedding via `speakeronnx` (192-dim L2-normalized vectors). Each teacher enrolls by reading 3–5 sentences; only their voice passes the similarity threshold
- **Command Matching** — Three strategies: exact, keyword (substring), or fuzzy (SequenceMatcher ratio). Falls back through the chain automatically
- **Push-to-Talk** — Global hotkey (`Ctrl+Alt+V`) for hands-free toggle; also supports pure voice wake via VAD
- **Multi-Teacher** — Register, select, and delete teacher profiles at runtime through the settings dialog
- **i18n** — English and Chinese UI; tray, settings, pipeline logs all switch via config
- **Minimal GUI** — System tray icon with context menu (Status, Settings, Mute, Quit); settings window with Voice Recognition / General / About tabs

## Architecture

```
Microphone ─► AudioCapture ─► SileroVAD ─► SpeakerVerifier ─► ASR ─► CommandMatcher ─► Action
                                                                    │
                                                          (SenseVoice / Vosk)
```

1. **AudioCapture** reads 16 kHz PCM blocks from the microphone
2. **SileroVAD** runs an ONNX neural network on each block, accumulating speech segments
3. **SpeakerVerifier** extracts a CAM++ embedding and compares it to the enrolled teacher's profile
4. **ASR** (SenseVoice or Vosk) transcribes the verified speech segment to text
5. **CommandMatcher** finds the best-matching command (exact → keyword → fuzzy)
6. **Action** executes the command — keyboard shortcut, system call, or UI action

All components are decoupled and wired together by `VoicePipeline` in `voirol/core/pipeline.py`.

## Supported Commands

| Category | Command | Action |
|---|---|---|
| Slide control | `next_page`, `prev_page` | → / ← arrow key |
| Display | `black_screen`, `white_screen` | Monitor off / fullscreen white window |
| Application | `open_whiteboard`, `open_browser`, `open_file` | mspaint, browser, file dialog |
| Audio | `volume_up`, `volume_down`, `mute` | System volume ±5, mute toggle |
| View | `fullscreen`, `esc` | F11, Escape |
| Input | `enter`, `space` | Enter, Space |

Chinese keyword lists accompany each command (e.g. `下一页` / `下一张` for `next_page`).

## Getting Started

### Prerequisites

- **Python 3.10+**
- **Windows 10/11**
- 4 GB RAM minimum

### Install

```bash
git clone <repo-url>
cd VoirolClass
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Configure

Edit `config.toml` to set language, microphone device, and ASR engine:

```toml
[general]
language = "en"         # or "zh"

[asr]
engine = "sensevoice"   # or "vosk"
```

The first run will automatically download the Silero VAD model (`models/silero_vad.onnx`) via mirror links.

### Run

```bash
.venv\Scripts\python main.py
```

A tray icon appears in the taskbar. Right-click to open Settings, register a teacher, and start using voice commands.

### Enrollment

1. Right-click tray icon → **Settings...**
2. Go to **Voice Recognition** tab → **Register New Teacher**
3. Enter a name and read the 5 sentences aloud when prompted
4. The system extracts your voiceprint and saves it

After enrollment, select your profile and start speaking. Only your voice will trigger commands.

## Configuration

Key settings in `config.toml`:

| Section | Key | Default | Description |
|---|---|---|---|
| `[general]` | `language` | `en` | UI language (`en` / `zh`) |
| `[vad]` | `threshold` | `0.25` | Speech probability threshold |
| | `min_speech_duration` | `0.5` | Seconds of speech to trigger |
| | `silence_duration` | `1.0` | Seconds of silence to end utterance |
| `[voice]` | `verification_threshold` | `0.45` | Similarity threshold for speaker match |
| | `model_path` | `campplus-zh-en` | speakeronnx model name |
| `[asr]` | `engine` | `sensevoice` | `sensevoice`, `vosk`, or `baidu` (stub) |
| `[commands]` | `match_mode` | `fuzzy` | `exact` / `keyword` / `fuzzy` |
| | `fuzzy_threshold` | `0.8` | SequenceMatcher ratio |
| `[hotkey]` | `push_to_talk` | `ctrl+alt+v` | PTT hotkey |
| `[ui]` | `font_size` | `13` | Font size (px) |
| | `border_radius` | `5` | Widget corner radius (px) |

## Project Structure

```
voirol/
├── asr/                  # SenseVoice & Vosk ASR engines
├── audio/                # Capture, VAD, preprocessing
├── command/              # Command registry, matcher, actions
├── core/                 # Config & VoicePipeline
├── gui/                  # System tray & settings dialog (PyQt6)
├── utils/                # i18n, logging, download helpers
└── voice/                # Speaker verification & enrollment
```

## Tech Stack

| Component | Library | Notes |
|---|---|---|
| GUI | PyQt6 | System tray + settings dialog |
| Audio capture | sounddevice | Callback-based PCM stream |
| VAD | Silero VAD ONNX | via onnxruntime |
| ASR | SenseVoiceSmall ONNX / Vosk | Both offline |
| Speaker verification | speakeronnx | CAM++ model, 192-dim embeddings |
| Command execution | pyautogui | Keyboard/mouse simulation |
| Hotkeys | keyboard | Global hotkey registration |
| i18n | Custom dict | English & Chinese built-in |

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
