<div align="center">
  <img src="VoirolClass.png" width="512" alt="VoirolClass">

  # VoirolClass

  **面向教师的语音控制教室辅助工具。使用自然语音即可控制幻灯片、屏幕、音量及应用程序，实现免提操作。**

  [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)](https://www.python.org/)
  [![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
  [![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey?style=flat-square)](https://www.microsoft.com/windows)
  [![Version](https://img.shields.io/github/v/release/ChidcGithub/VoirolClass?style=flat-square&color=white)](https://github.com/ChidcGithub/VoirolClass/releases)
  [![Build](https://img.shields.io/github/actions/workflow/status/ChidcGithub/VoirolClass/build.yml?style=flat-square&label=build)](https://github.com/ChidcGithub/VoirolClass/actions)
  [![ASR](https://img.shields.io/badge/ASR-SenseVoice%20(离线)-informational?style=flat-square)](https://github.com/modelscope/FunASR)
  [![声纹验证](https://img.shields.io/badge/声纹-CAM%2B%2B-informational?style=flat-square)](https://github.com/BlueSpaceX/speakeronnx)
  [![AI Agent](https://img.shields.io/badge/Agent-LLM%20驱动-8A2BE2?style=flat-square)](voirol/agent/)
  [![TTS](https://img.shields.io/badge/TTS-Moss%20Nano-ff69b4?style=flat-square)](voirol/tts/)
  [![PRs Welcome](https://img.shields.io/badge/PR-欢迎-brightgreen?style=flat-square)](https://github.com/ChidcGithub/VoirolClass/pulls)
  [![English](https://img.shields.io/badge/English-blue?style=flat-square)](README.md)

  [功能特点](#功能特点) • [快速开始](#快速开始) • [架构](#架构) • [支持指令](#支持指令) • [配置说明](#配置说明) • [项目结构](#项目结构) • [技术栈](#技术栈)

</div>

> [!TIP]
> 如果你擅长 UI 设计并且有兴趣一起改进这个项目，非常欢迎联系我！贡献指南请参阅 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 功能特点

| 功能 | 说明 |
|------|------|
| **语音活动检测 (VAD)** | Silero VAD ONNX，灵敏度可配置。环形缓冲区避免截断句首 |
| **离线 ASR** | SenseVoiceSmall 纯 ONNX Runtime，无云端依赖，CPU 流畅运行 |
| **声纹验证** | CAM++ 嵌入（192 维，`speakeronnx`）。老师朗读 3–5 句注册，仅匹配者通过 |
| **指令匹配** | 三级策略：精确 → 关键词 → 模糊匹配；可回退到 AI 语义匹配（DeepSeek / OpenAI） |
| **AI Agent** | LLM 驱动的桌面操控代理：屏幕 OCR、鼠标键盘控制、文件搜索、应用启动、多步骤任务 |
| **文字转语音 (TTS)** | 本地 Moss TTS Nano 服务，支持中文语音输出 |
| **语音唤醒 + 快捷键** | 全局热键 `Ctrl+Alt+V` 或纯 VAD 语音唤醒 |
| **多老师支持** | 运行时注册、选择、删除老师声纹档案 |
| **国际化** | 英文和中文界面，运行时切换 |

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

右键托盘图标 → **设置...** → 注册老师。开始说出指令："下一页"、"黑屏"、"打开百度"。

<details>
<summary><b>详细安装</b></summary>

```bash
git clone https://github.com/ChidcGithub/VoirolClass.git
cd VoirolClass
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

编辑 `config.toml` 设置语言和麦克风设备，然后运行：

```bash
python main.py
```

首次运行会自动下载所需模型。

</details>

## 架构

```
麦克风 ─► AudioCapture ─► SileroVAD ─► SpeakerVerifier ─► ASR ─► CommandMatcher ─► 执行动作
                                                                       │
                                                                └─ AIMatcher (AI 回退)
                                                                       │
                                                                └─ AgentEngine (多步骤)
```

1. **AudioCapture** 以 16 kHz PCM 从麦克风读取音频块
2. **SileroVAD** 运行 ONNX 神经网络检测语音段
3. **SpeakerVerifier** 提取 CAM++ 嵌入并与已注册老师声纹比对
4. **ASR**（SenseVoice）将语音片段转录为文字
5. **CommandMatcher** 寻找最佳匹配指令（精确 → 关键词 → 模糊）
6. **AIMatcher**（可选）回退到 LLM 语义匹配
7. **AgentEngine**（可选）处理复杂多步骤任务（屏幕 OCR + 电脑操控）
8. **Action** 执行指令 — 键盘快捷键、系统调用或界面操作

所有组件通过 `VoicePipeline`（`voirol/core/pipeline.py`）连接。

## 支持指令

| 类别 | 指令 | 操作 |
|------|------|------|
| 幻灯片控制 | `next_page`, `prev_page` | `→` / `←` |
| 显示 | `black_screen`, `white_screen` | 关闭显示器 / 全屏白板 |
| 应用 | `open_whiteboard`, `open_browser`, `open_file`, `open` (AI 路由) | 启动软件和文件 |
| 音频 | `volume_up`, `volume_down`, `mute` | 音量 ±5，静音 |
| 视图 | `fullscreen`, `esc` | `F11`, `Esc` |
| 输入 | `enter`, `space` | `Enter`, `Space` |
| AI Agent | `电脑操作` `帮我找到...` `screen` | 多步骤任务执行 |

每个指令配有中文关键词（如 `下一页` / `下一张` 对应 `next_page`）。

## 配置说明

`config.toml` 主要配置项：

| 段落 | 键 | 默认值 | 说明 |
|------|----|--------|------|
| `[general]` | `language` | `en` | UI 语言 (`en` / `zh`) |
| `[vad]` | `threshold` | `0.25` | 语音概率阈值 |
| | `silence_duration` | `1.0` | 判定结束的静音秒数 |
| `[voice]` | `verification_threshold` | `0.45` | 声纹相似度阈值 |
| `[asr]` | `engine` | `sensevoice` | `sensevoice` / `baidu` / `azure` / `tencent` |
| `[commands]` | `match_mode` | `fuzzy` | `exact` / `keyword` / `fuzzy` |
| | `fuzzy_threshold` | `0.8` | SequenceMatcher 比例 |
| `[hotkey]` | `push_to_talk` | `ctrl+alt+v` | 一键通话快捷键 |
| `[ai]` | `enabled` | `false` | 启用 AI 回退匹配 |
| | `api_url` | `https://api.deepseek.com/v1` | OpenAI 兼容 API |
| | `model` | `deepseek-chat` | 模型名称 |
| `[agent]` | `enabled` | `false` | 启用 AI Agent 多步骤任务 |
| | `max_steps` | `30` | 单任务最大执行步数 |
| `[tts]` | `enabled` | `false` | 启用文字转语音输出 |

完整配置参考 `config.toml.example`。

## 项目结构

```
voirol/
├── ai/             # LLM 集成（OpenAI 兼容 API，语义匹配）
├── agent/          # AI 代理（屏幕 OCR、鼠标键盘、文件操作、任务执行）
├── asr/            # 语音识别（SenseVoice、百度、Azure、腾讯云）
├── audio/          # 音频采集、VAD、预处理
├── command/        # 指令注册、匹配、执行（打开文件、浏览器、音量等）
├── core/           # 配置加载 & VoicePipeline（音频 → 指令编排器）
├── gui/            # PyQt6：系统托盘、设置、启动画面、浮动胶囊
├── tts/            # 文字转语音（Moss TTS Nano）
├── utils/          # 国际化、日志、HTTP 下载
└── voice/          # 声纹验证和注册（CAM++，档案管理）
```

## 技术栈

| 组件 | 库 | 备注 |
|------|----|------|
| GUI | PyQt6 | 系统托盘、设置、OpenGL 指示器 |
| 音频采集 | sounddevice | 基于回调的 16 kHz PCM 流 |
| VAD | Silero VAD ONNX | 通过 onnxruntime |
| ASR | SenseVoiceSmall ONNX | 完全离线，CPU |
| 声纹验证 | speakeronnx | CAM++，192 维嵌入 |
| 指令执行 | pyautogui | 键盘 & 鼠标模拟 |
| AI/LLM | OpenAI 兼容 API | DeepSeek / OpenAI 等 |
| OCR | pytesseract | 屏幕文字提取（Agent） |
| 热键 | keyboard | 全局快捷键注册 |
| 国际化 | 自定义字典 | 内置英文和中文 |

## 开源库

VoirolClass 依赖以下开源项目，感谢它们的贡献。

| 库 | 许可协议 | 说明 |
|----|----------|------|
| [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) | GPL v3 | 跨平台 GUI 框架 |
| [sounddevice](https://python-sounddevice.readthedocs.io/) | MIT | 音频采集与播放 |
| [soundfile](https://python-soundfile.readthedocs.io/) | BSD-3-Clause | 音频文件读写 |
| [onnxruntime](https://github.com/microsoft/onnxruntime) | MIT | 跨平台 ML 推理引擎 |
| [Silero VAD](https://github.com/snakers4/silero-vad) | MIT | 语音活动检测 |
| [SenseVoice](https://github.com/modelscope/FunASR) | MIT | 语音识别引擎 |
| [CAM++ / speakeronnx](https://github.com/BlueSpaceX/speakeronnx) | Apache 2.0 | 声纹验证 |
| [pyautogui](https://github.com/asweigart/pyautogui) | BSD-3-Clause | 键盘鼠标自动化 |
| [pytesseract](https://github.com/madmaze/pytesseract) | Apache 2.0 | OCR 引擎封装 |
| [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) | Apache 2.0 | OCR 引擎 |
| [Pillow](https://python-pillow.org/) | Historical | 图像处理 |
| [keyboard](https://github.com/boppreh/keyboard) | MIT | 全局快捷键 |
| [scipy](https://scipy.org/) | BSD-3-Clause | 信号处理 |
| [numpy](https://numpy.org/) | BSD-3-Clause | 数值计算 |
| [requests](https://requests.readthedocs.io/) | Apache 2.0 | HTTP 客户端 |
| [toml](https://github.com/uiri/toml) | MIT | TOML 配置解析 |
| [MOSS TTS Nano](https://github.com/OpenMOSS/MOSS-TTS-Nano) | Apache 2.0 | 文字转语音引擎 |
