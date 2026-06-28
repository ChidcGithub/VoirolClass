![VoirolClass](VoirolClass.png)

# VoirolClass

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows%2010%2F11-lightgrey)](https://www.microsoft.com/windows)
[![Version](https://img.shields.io/badge/version-0.0.1-orange)]()
[![Build](https://github.com/ChidcGithub/VoirolClass/actions/workflows/build.yml/badge.svg)](https://github.com/ChidcGithub/VoirolClass/actions/workflows/build.yml)

> [English Documentation](README.md)

> [!TIP]
> 如果你擅长 UI 设计并且有兴趣一起改进这个项目，非常欢迎联系我！

VoirolClass 是一款面向教师的语音控制教室辅助工具。使用自然语音即可控制幻灯片、屏幕、音量及应用程序，实现免提操作。

## 功能特点

- **语音活动检测 (VAD)** — 基于 Silero VAD ONNX，灵敏度、语音/静音时长均可配置，环形缓冲区保留约 1 秒历史音频，避免截断句首
- **双 ASR 引擎** — SenseVoiceSmall（纯 ONNX Runtime，主引擎）或 Vosk-Kaldi（备用），完全离线运行
- **声纹验证** — 基于 CAM++ 嵌入（`speakeronnx`，192 维 L2 归一化向量）。每位老师朗读 3-5 句话完成注册；仅相似度超过阈值的语音才通过验证
- **指令匹配** — 三种策略：精确、关键词（子串）、模糊（SequenceMatcher 比例），自动顺序降级，再回退到 **AI 语义匹配**（DeepSeek/OpenAI）
- **AI 语义匹配** — 可选的 DeepSeek/OpenAI 集成。关键词和模糊匹配均失败时，将转录文本发送给 LLM 推断用户意图，匹配最合适的指令
- **语音+按键双模式** — 全局快捷键（`Ctrl+Alt+V`）一键通话，也支持纯语音唤醒
- **多老师支持** — 运行时通过设置界面注册、选择、删除老师
- **国际化 (i18n)** — 支持英文和中文界面，托盘、设置、日志均跟随配置切换
- **最小化 GUI** — 系统托盘图标 + 右键菜单（状态、设置、静音、退出）；设置窗口包含语音识别/通用/关于三个标签页

## 架构

```
麦克风 ─► AudioCapture ─► SileroVAD ─► SpeakerVerifier ─► ASR ─► CommandMatcher ─► 执行动作
                                                                           │
                                                                 (SenseVoice / Vosk)
                                                                           │
                                                                (回退)     │
                                                                           ▼
                                                                     AIMatcher (AI)
                                                                    DeepSeek/OpenAI
```

1. **AudioCapture** 以 16 kHz PCM 格式从麦克风读取音频块
2. **SileroVAD** 在每个音频块上运行 ONNX 神经网络，累积语音片段
3. **SpeakerVerifier** 提取 CAM++ 嵌入并与已注册老师的声纹模型对比
4. **ASR**（SenseVoice 或 Vosk）将验证通过的语音片段转录为文字
5. **CommandMatcher** 寻找最佳匹配指令（精确 → 关键词 → 模糊）
6. **AIMatcher**（可选，可配置）当关键词匹配失败时，回退到 LLM（DeepSeek/OpenAI），解析 JSON 响应确定指令
7. **Action** 执行指令 — 键盘快捷键、系统调用或界面操作

所有组件解耦并通过 `VoicePipeline`（`voirol/core/pipeline.py`）连接。

## 支持指令

| 类别 | 指令 | 动作 |
|---|---|---|
| 幻灯片控制 | `next_page`, `prev_page` | → / ← 方向键 |
| 显示 | `black_screen`, `white_screen` | 关闭显示器 / 全屏白窗口 |
| 应用程序 | `open_whiteboard`, `open_browser`, `open_file` | 画图、浏览器、文件选择 |
| 音频 | `volume_up`, `volume_down`, `mute` | 系统音量 ±5，静音切换 |
| 视图 | `fullscreen`, `esc` | F11，Escape |
| 输入 | `enter`, `space` | 回车，空格 |

每个指令都配有中文关键词列表（如 `下一页` / `下一张` 对应 `next_page`）。

## 快速开始

### 系统要求

- **Python 3.10+**
- **Windows 10/11**
- 4 GB 及以上内存

### 安装

```bash
git clone <仓库地址>
cd VoirolClass
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 配置

编辑 `config.toml` 设置语言、麦克风设备和 ASR 引擎：

```toml
[general]
language = "zh"          # "en" 或 "zh"

[asr]
engine = "sensevoice"    # 或 "vosk"
```

首次运行会自动通过镜像链接下载 Silero VAD 模型（`models/silero_vad.onnx`）。

### 运行

```bash
.venv\Scripts\python main.py
```

任务栏会出现托盘图标。右键打开设置，注册老师后即可使用语音指令。

### 注册老师

1. 右键托盘图标 → **设置...**
2. 进入 **语音识别** 标签页 → **注册新老师**
3. 输入姓名，按照提示依次朗读 5 个句子
4. 系统会提取您的声纹并保存

注册后选择您的档案并开始说话，只有您的声音才能触发指令。

## 配置说明

`config.toml` 主要配置项：

| 段落 | 键 | 默认值 | 说明 |
|---|---|---|---|
| `[general]` | `language` | `en` | UI 语言（`en` / `zh`） |
| `[vad]` | `threshold` | `0.25` | 语音概率阈值 |
| | `min_speech_duration` | `0.5` | 触发 VAD 的最短语音时长 |
| | `silence_duration` | `1.0` | 判定结束的静音时长 |
| `[voice]` | `verification_threshold` | `0.45` | 声纹匹配相似度阈值 |
| | `model_path` | `campplus-zh-en` | speakeronnx 模型名称 |
| | `ring_buffer_seconds` | `2.0` | VAD 触发前保留的历史音频时长（秒） |
| `[asr]` | `engine` | `sensevoice` | `sensevoice` / `vosk` / `baidu` |
| | `mode` | `offline` | 识别模式（`offline` / `online`） |
| `[commands]` | `match_mode` | `fuzzy` | `exact` / `keyword` / `fuzzy` |
| | `fuzzy_threshold` | `0.8` | SequenceMatcher 比例 |
| `[hotkey]` | `push_to_talk` | `ctrl+alt+v` | 一键通话快捷键 |
| `[ui]` | `font_size` | `13` | 字体大小（px） |
| | `border_radius` | `5` | 控件圆角半径（px） |
| `[ai]` | `enabled` | `false` | 启用 AI 回退匹配 |
| | `api_url` | `https://api.deepseek.com/v1` | OpenAI 兼容 API 地址 |
| | `model` | `deepseek-chat` | 模型名称 |
| | `temperature` | `0.1` | LLM 温度 (0.0–2.0) |

## 项目结构

```
voirol/
├── ai/                   # AI 指令匹配 (DeepSeek/OpenAI)
├── asr/                  # SenseVoice 和 Vosk ASR 引擎
├── audio/                # 音频采集、VAD、预处理
├── command/              # 指令注册、匹配、执行
├── core/                 # 配置和 VoicePipeline
├── gui/                  # 系统托盘和设置界面 (PyQt6)
├── utils/                # 国际化、日志、下载工具
└── voice/                # 声纹验证和注册
```

## 技术栈

| 组件 | 库 | 备注 |
|---|---|---|
| GUI | PyQt6 | 系统托盘 + 设置对话框 |
| 音频采集 | sounddevice | 基于回调的 PCM 流 |
| VAD | Silero VAD ONNX | 通过 onnxruntime |
| ASR | SenseVoiceSmall ONNX / Vosk | 均离线运行 |
| 声纹验证 | speakeronnx | CAM++ 模型，192 维嵌入 |
| 指令执行 | pyautogui | 键盘/鼠标模拟 |
| AI 匹配 | DeepSeek / OpenAI API | 可选的 LLM 语义回退匹配 |
| 快捷键 | keyboard | 全局热键注册 |
| 国际化 | 自定义字典 | 内置英文和中文 |

## 许可

本项目基于 MIT 许可发布 — 详见 [LICENSE](LICENSE) 文件。
