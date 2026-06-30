# VoirolClass Rust 迁移规划

## 一、FluidVoice vs VoirolClass 对比

| 维度 | FluidVoice / FluidAudio | VoirolClass |
|---|---|---|
| 语言 | Swift 99.7% | Python 100% |
| 平台 | macOS 15+, Apple Silicon | Windows 10/11 |
| ASR 引擎 | Parakeet TDT (CoreML), Nemotron 3.5, Whisper | SenseVoiceSmall ONNX, Vosk |
| VAD | Silero VAD (CoreML) | Silero VAD (ONNX) |
| 说话人识别 | LS-EEND, Sortformer, Pyannote+WeSpeaker | speakeronnx CAM++ |
| TTS | Kokoro 82M, PocketTTS | 无 |
| AI 增强 | Fluid Intelligence (私有) + OpenAI/Groq | OpenAI/DeepSeek 指令匹配 |
| 推理后端 | CoreML (ANE), Metal | ONNX Runtime CPU |
| 性能 | ~190x RTF on M4 Pro | 受 Python GIL + CPU 限制 |
| 许可证 | FluidVoice GPLv3, FluidAudio Apache 2.0 | GPLv3 |

## 二、FluidVoice 关键技术

### 可移植的算法

| 算法 | 来源文件 | 行数 | 移植难度 |
|---|---|---|---|
| TDT Decoder | `TdtDecoderV3.swift` | 40K | 高 |
| Sliding Window ASR | `SlidingWindowAsrManager.swift` | 32K | 中 |
| CTC Decoder | `CtcDecoder.swift` | 10K | 中 |
| BK-Tree 词汇纠错 | `BKTree.swift` | 4K | 低 |
| Custom Vocabulary Rescoring | `VocabularyRescorer.swift` | 8K | 中 |

**注意**: FluidAudio 代码是 Swift，但算法本身是通用的。关键的 TDT/CTC 解码逻辑可以用 Rust 重写。

### FluidAudio SDK (Apache 2.0)

- ASR: Parakeet TDT v3 (25 语言, ~500MB), Parakeet EOU (流式), Qwen3-ASR
- VAD: Silero VAD
- Speaker Diarization: LS-EEND, Sortformer, Pyannote+WeSpeaker
- TTS: Kokoro 82M, PocketTTS
- 推理: CoreML (ANE), 仅 macOS/iOS

**Windows 可用性**: fluidaudio-rs 仅支持 macOS。但有 `fluid-server` (Python) 和 Windows 上的 ONNX Runtime 替代方案。

## 三、ONNX 模型 Rust 兼容性

### 3.1 Silero VAD — 直接可用

已有生产级 Rust crate:

```toml
silero = "0.4"  # 内置 ONNX 模型，无需额外下载
```

- 模型: bundled `silero_vad.onnx` (与 Python 版同一文件)
- ONNX Runtime: 通过 `ort` 2.0.0-rc.12
- Windows 加速: 支持 DirectML (`features = ["directml"]`)
- API: `Session::bundled()` → `infer()` → `SpeechSegmenter`
- 输入: `(1, 576)` float32, `(1,)` int64 sr, `(2, 1, 128)` float32 state
- 输出: `(1, 1)` float32 probability, `(2, 1, 128)` float32 state

结论: 零迁移成本，直接替换 Python 实现。

### 3.2 SenseVoiceSmall INT8 — 已有参考实现

`sensevoice-rs` crate (v0.1.7, MIT 许可):

```toml
sensevoice-rs = "0.1.7"
```

- 后端: 支持 `ort` (ONNX Runtime) 和 `rknn` (Rockchip NPU)
- ONNX Runtime: 使用 `ort` 2.0.0-rc.10
- 模型: 支持 `.onnx` (ONNX) 和 `.pt` (Candle) 两种格式
- INT8 量化: ONNX Runtime 原生支持 S8S8/U8U8 量化

模型输入输出:

| 张量 | 名称 | 形状 | 类型 |
|---|---|---|---|
| LFR 特征 | `x` | `(1, T, 560)` | float32 |
| 特征长度 | `x_length` | `(1,)` | int32 |
| 语言 ID | `language` | `(1,)` | int32 |
| 文本规范化 | `text_norm` | `(1,)` | int32 |

特征提取: 80-dim fbank + LFR (window=7, shift=6) → 560-dim
解码: CTC greedy decoding (argmax + blank removal)

结论: `sensevoice-rs` 已验证 ONNX 路径可行，可直接使用或参考。

### 3.3 CAM++ 说话人验证 — 标准 ONNX

模型: `3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx`

- 输入: `(1, T, 80)` float32 (80-dim fbank)
- 输出: 192-dim L2-normalized embedding
- 需要移植: 80-dim log-Mel filterbank + CMN (约 100 行 Rust)

结论: ONNX 模型本身兼容，需移植 fbank 特征提取。

### 3.4 Vosk — 不兼容，需替代

Vosk 使用 Kaldi C++ 后端，不是 ONNX 模型。

替代方案: 用 SenseVoiceSmall 完全替代 Vosk (推荐)。

### 3.5 INT8 量化兼容性

| 特性 | `ort` 支持情况 |
|---|---|
| INT8 量化推理 | 原生支持 (S8S8, U8U8) |
| QDQ 量化模型 | 完全支持 |
| QOperator 量化模型 | x86-64 上较慢，不推荐 |
| CPU INT8 加速 | 需 VNNI 指令集 (较新 CPU) |
| GPU INT8 加速 | 需 Tensor Core (NVIDIA) |

## 四、Rust 生态工具链

| 模块 | 推荐 Crate | 版本 | Stars | Windows 支持 |
|---|---|---|---|---|
| ONNX 推理 | `ort` | 2.0.0-rc.12 | 2.1k | CUDA/DirectML/OPENVINO |
| VAD | `silero` | 0.4.0 | 新 | bundled ONNX, DirectML |
| 音频采集 | `cpal` | 0.18.0 | 4k | WASAPI (事件驱动低延迟) |
| 托盘图标 | `tray-icon` | 0.24.1 | - | Win32 原生 |
| 菜单 | `muda` | 0.19.3 | 385 | Win32 原生 |
| 全局热键 | `global-hotkey` | latest | - | Win32 |
| HTTP 客户端 | `reqwest` | 0.13.4 | 11.6k | rustls/native-tls |
| 异步运行时 | `tokio` | 1.x | - | 完整 Windows 支持 |
| 序列化 | `serde` + `serde_json` | 1.x | - | - |
| Windows API | `windows-sys` | 0.59+ | - | - |
| TOML 配置 | `toml` | 0.8 | - | - |
| 日志 | `tracing` + `tracing-subscriber` | - | - | - |

## 五、架构设计

```
voirol-class-rs/
├── Cargo.toml
├── src/
│   ├── main.rs                    // 入口 + tokio 运行时
│   ├── audio/
│   │   ├── mod.rs
│   │   ├── capture.rs             // cpal WASAPI 采集
│   │   ├── resample.rs            // 重采样到 16kHz
│   │   └── ring_buffer.rs         // ~1s 环形缓冲
│   ├── vad/
│   │   ├── mod.rs
│   │   └── silero.rs              // silero crate 封装
│   ├── asr/
│   │   ├── mod.rs
│   │   ├── sensevoice.rs          // SenseVoiceSmall ONNX
│   │   └── cloud/
│   │       ├── mod.rs
│   │       ├── baidu.rs
│   │       ├── azure.rs
│   │       └── tencent.rs
│   ├── speaker/
│   │   ├── mod.rs
│   │   └── verify.rs              // CAM++ ONNX
│   ├── command/
│   │   ├── mod.rs
│   │   ├── matcher.rs             // 关键字 + 模糊匹配
│   │   ├── ai_matcher.rs          // OpenAI/DeepSeek
│   │   └── router.rs              // 打开文件/网页/应用
│   ├── ui/
│   │   ├── mod.rs
│   │   ├── tray.rs                // tray-icon + muda
│   │   ├── indicator.rs           // 玻璃风格指示器
│   │   ├── settings.rs            // 设置窗口
│   │   └── splash.rs              // 启动画面
│   ├── hotkey.rs                  // global-hotkey
│   ├── i18n.rs                    // 国际化
│   ├── config.rs                  // TOML 配置
│   └── logger.rs                  // tracing 日志
├── assets/
│   ├── img/
│   ├── fonts/
│   └── models/                    // ONNX 模型
└── build.rs                       // 编译脚本
```

## 六、各模块实现方案

### 6.1 音频采集 (cpal)

```rust
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};

let host = cpal::default_host(); // 自动选择 WASAPI
let device = host.default_input_device().unwrap();
let config = StreamConfig {
    channels: 1,
    sample_rate: SampleRate(16000),
    buffer_size: cpal::BufferSize::Fixed(1024),
};
// 事件驱动，低延迟
```

### 6.2 VAD (silero crate)

```rust
use silero::{Session, StreamState, SpeechSegmenter};

let session = Session::bundled()?;
let mut stream = StreamState::new();
let mut segmenter = SpeechSegmenter::default();

let prob = session.infer(&chunk, &mut stream)?;
segmenter.feed(prob);
if let Some(seg) = segmenter.poll() {
    // 语音段开始/结束
}
```

### 6.3 ASR (ort crate)

```rust
use ort::{Session, SessionBuilder};

let session = SessionBuilder::new()?
    .with_optimization_level(GraphOptimizationLevel::Level3)?
    .commit_from_file("models/sensevoice.onnx")?;

let input = preprocess_audio(samples);
let outputs = session.run(ort::inputs!["input" => input])?;
let text = postprocess(&outputs);
```

### 6.4 说话人验证 (ort)

```rust
let embedding = extract_embedding(audio, &session)?;
let similarity = cosine_sim(&embedding, &teacher_embedding);
let verified = similarity > threshold;
```

### 6.5 AI 命令匹配 (reqwest)

```rust
use reqwest::Client;

let client = Client::new();
let resp = client.post(&api_url)
    .header("Authorization", format!("Bearer {}", api_key))
    .json(&json!({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"}
    }))
    .send().await?;
```

### 6.6 UI 系统

推荐纯 Win32 方案 (最小体积):
- 托盘: `tray-icon` crate
- 菜单: `muda` crate
- 热键: `global-hotkey` crate
- 指示器: `windows-sys` 创建透明窗口 + Direct2D
- 设置: Win32 对话框

## 七、渐进迁移路线

### Phase 0: 基准测试 (1-2 周)

1. 用 Python 版本测量各阶段耗时:
   - 音频采集 → VAD → ASR → 说话人验证 → 命令匹配
2. 确认瓶颈在 Python GIL 还是 ONNX 推理
3. 在学校电脑 (4GB RAM, 低配 CPU) 上测试

### Phase 1: Rust 最小原型 (2-3 周)

创建 Rust 项目，实现「音频采集 + Silero VAD」最小 demo:

```toml
[dependencies]
ort = "=2.0.0-rc.12"
silero = "0.4"
cpal = "0.18"
tokio = { version = "1", features = ["full"] }
```

验证:
- WASAPI 音频采集在目标电脑正常工作
- Silero VAD 推理正确
- ONNX Runtime 动态库加载正常

### Phase 2: Rust 核心库 (6-8 周)

```
- [ ] cpal 音频采集 (WASAPI, 16kHz mono)
- [ ] silero VAD (帧级语音检测)
- [ ] SenseVoiceSmall ONNX ASR
- [ ] CAM++ 说话人验证 ONNX
- [ ] 关键字 + 模糊命令匹配
- [ ] AI 命令匹配 (reqwest)
- [ ] 环形缓冲 (~1s 音频历史)
- [ ] 多教师管理 (config.toml)
- [ ] 云端 ASR (百度/Azure/腾讯)
```

### Phase 3: 原生 Win32 UI (4-6 周)

```
- [ ] 系统托盘 (tray-icon)
- [ ] 右键菜单 (muda)
- [ ] 全局热键 Ctrl+Alt+V (global-hotkey)
- [ ] 玻璃风格指示器 (Win32 透明窗口)
- [ ] 设置窗口 (Win32 dialog)
- [ ] 启动画面
- [ ] i18n 支持
```

### Phase 4: 打包与分发 (2-3 周)

```
- cargo build --release
- NSIS 打包
- 体积: ~5-10MB (vs Python PyInstaller ~50MB)
- 启动速度: <100ms (vs Python ~2-3s)
```

## 八、性能预估

| 指标 | Python (当前) | Rust (预期) | 提升 |
|---|---|---|---|
| 启动时间 | 2-3s | <100ms | 20-30x |
| 内存占用 | ~200MB | ~30-50MB | 4-6x |
| VAD 延迟 | ~10ms | ~1ms | 10x |
| ASR 延迟 | ~50ms | ~10ms | 5x |
| 二进制体积 | ~50MB | ~5-10MB | 5-10x |
| 无 GIL 限制 | 有 | 无 | - |

## 九、Windows 执行提供者

| 执行提供者 | Windows 支持 | 硬件要求 | 适用场景 |
|---|---|---|---|
| CPU | 默认 | 任何 | 所有模型 |
| DirectML | 原生 | DirectX 12 GPU | 学校电脑有独显时 |
| CUDA | 需安装 | NVIDIA GPU | 高端配置 |
| TensorRT | 需安装 | NVIDIA RTX | 最低延迟 |
| OpenVINO | 原生 | Intel CPU/GPU/NPU | Intel 处理器 |

学校电脑建议: 默认 CPU，检测到 DirectX 12 GPU 时自动切换 DirectML。

## 十、风险与缓解

| 风险 | 影响 | 缓解方案 |
|---|---|---|
| Rust 学习曲线 | 开发速度慢 | 先用 Python FFI 桥接，逐步替换 |
| Windows WASAPI 兼容性 | 音频采集问题 | cpal 已有成熟 WASAPI 后端 |
| ONNX 模型兼容性 | 推理结果不一致 | ort 与 Python onnxruntime 共享同一 ONNX 文件 |
| 学校电脑无 Rust 编译环境 | 无法构建 | 交叉编译或 CI/CD 预编译 |
| 4GB RAM 限制 | 模型加载慢 | 模型懒加载 + 内存映射 |
| Vosk 不兼容 ONNX | Fallback 不可用 | 用 SenseVoiceSmall 完全替代 Vosk |

## 十一、从 FluidVoice 可借鉴的设计

1. **Model Registry**: 下载管理、镜像支持 (可直接移植)
2. **Streaming ASR**: 滑动窗口 + 增量解码 (算法可移植)
3. **Custom Vocabulary**: BK-Tree 词汇纠错 (可直接移植)
4. **EOU 检测**: Parakeet EOU 流式端点检测 (算法可移植)
5. **TDT Decoder**: Token-and-Duration Transducer (复杂，需评估)
6. **Per-App Config**: 不同应用不同配置 (架构可参考)
7. **Onboarding Flow**: 语言选择 + 模型下载 + 试用 (UX 可参考)

## 十二、当前 Python 版本待修复项

在 Rust 迁移前，Python 版本仍有以下待处理项:

1. DPI 警告 (`SetProcessDpiAwarenessContext() failed`) — 可尝试 `qt.conf`
2. `config.toml` 示例文件需要更新 (添加 AI 配置示例)
3. `--add-data "qt.conf;."` 需添加到 build.yml
