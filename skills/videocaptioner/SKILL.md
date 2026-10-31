---
name: videocaptioner
display_name: 视频字幕生成
display_name_en: Video Captioner
description: '用 videocaptioner CLI 给视频加字幕：语音识别转写、LLM 润色断句、Bing/Google/LLM 翻译、把样式化字幕烧进画面或封装软字幕，也支持配音与在线视频下载。适用于「给视频加字幕」「把音频转成 srt」「翻译字幕」「做成中英双语字幕」「改字幕字体颜色」「下载视频再配字幕」等请求。This skill should be used when the user wants to add subtitles to a video, transcribe audio or video to text, translate subtitle files, customize subtitle appearance, or download and caption online videos. 触发词：加字幕、视频字幕、字幕翻译、双语字幕、转写、语音识别、srt、ass、硬字幕、软字幕、烧字幕、videocaptioner、captioner。'
description_zh: '基于 videocaptioner CLI 的一站式字幕工具：转写、润色、翻译、样式化烧录、配音、在线视频下载。'
description_en: 'One-stop video captioning via the videocaptioner CLI: transcribe, polish, translate, burn styled subtitles, dub, and download online videos.'
examples_zh:
  - '给这个视频加上中文字幕，字幕要好看一点，直接导出成片'
  - '把这个英文视频转写成 srt，再翻成中英双语字幕'
  - '这份 srt 的识别错字太多，帮我润色一下断句'
examples_en:
  - 'Add stylish Chinese subtitles to this video and export the finished file'
  - 'Transcribe this English video to srt and translate it into bilingual subtitles'
  - 'These ASR subtitles have too many errors, polish and re-split them'
version: 1.0.0
author: "个人开发者"
license: MIT
allowed-tools: Bash, Read, Write
agent_created: true
---

# VideoCaptioner CLI

封装 `videocaptioner` 命令行工具：语音识别 → 字幕润色断句 → 翻译 → 样式化烧录，一条命令走完全流程。

## 何时使用

- 用户要给视频**加字幕**
- 用户要把音视频**转写成文本/字幕**
- 用户要**翻译字幕**到另一种语言，或做**双语对照**
- 用户要**调整字幕外观**（字体、颜色、圆角背景）
- 用户要**下载在线视频**（YouTube、Bilibili 等）并配字幕
- 用户要做**视频配音**（TTS / 音色克隆）

## 第 0 步：先自检，别急着跑

```bash
videocaptioner doctor          # 检查 Python/ffmpeg/配置，有问题直接给出修复建议
videocaptioner <command> --help  # 以 --help 为准，示例只是常见组合
```

`doctor` 会检查 python、ffmpeg 等依赖并输出修复提示，失败时退出码为 4。
**每次执行前先跑 `--help` 确认参数**——CLI 迭代快，隐藏参数（`argparse.SUPPRESS`）不出现在帮助里。

## 安装（有一处硬约束）

```bash
pip install videocaptioner
```

**Python 版本必须 < 3.13、≥ 3.10**（包元数据 `Requires-Python: <3.13,>=3.10`）。
默认解释器是 3.13 及以上时会直接装失败。此时不要改系统 Python，用 3.12 建独立虚拟环境最稳：

```bash
# 1) 找一个 3.10–3.12 的解释器
py -0                      # Windows 列出已安装版本；Linux/macOS 用 ls /usr/bin/python3.*

# 2) 建虚拟环境并安装（以 Windows 3.12 为例）
"C:\路径\Python312\python.exe" -m venv .venv-vc
.venv-vc\Scripts\python -m pip install videocaptioner
.venv-vc\Scripts\videocaptioner doctor     # 验证

# macOS / Linux
python3.12 -m venv .venv-vc && .venv-vc/bin/pip install videocaptioner
```

若 `videocaptioner` 不在 PATH，用 `python -m videocaptioner <cmd>` 调用（包内带 `__main__.py`）。
uv 托管的 Python 受 PEP 668 保护，不能直接 `pip install`，必须先建 venv。

其它前置：

- **ffmpeg** 必需（抽音、时间轴、合成）：Windows `winget install --id Gyan.FFmpeg -e`；macOS `brew install ffmpeg`；Ubuntu `sudo apt install ffmpeg`
- 安装体积较大（含 PyQt5、yt-dlp、modelscope 等，约 47 个包），首次安装可能耗时数分钟
- **免费可用**：转写（bijian/jianying）、翻译（Bing/Google），无需任何 key
- **需要 LLM key**：字幕润色、重新断句、LLM 翻译。通过 `OPENAI_API_KEY` / `OPENAI_BASE_URL` 环境变量，或 `--api-key` / `--api-base` 传入

## 常见场景

### 1. 中文视频加英文字幕（全免费，一条命令）

```bash
videocaptioner process video.mp4 --asr bijian --translator bing --to en \
  --subtitle-mode hard --quality high -o output.mp4
```

### 2. 转写为 SRT（免费）

```bash
videocaptioner transcribe video.mp4 --asr bijian -o output.srt

# JSON 格式输出到目录（含词级时间戳时加 --word-timestamps）
videocaptioner transcribe video.mp4 --asr bijian --format json -o ./subtitles/
```

### 3. 翻译已有字幕

```bash
# Bing 免费翻译，译文在上、原文在下的双语输出
videocaptioner subtitle input.srt --translator bing --target-language en --layout target-above -o translated.srt

# Google 免费翻译，只保留译文
videocaptioner subtitle input.srt --translator google --target-language ja --no-optimize --layout target-only -o output_ja.srt

# LLM 翻译 + 反思模式（质量最高，需 key）
videocaptioner subtitle input.srt --translator llm --target-language en --reflect \
  --api-key $OPENAI_API_KEY -o output_en.srt

# 只润色识别错误，不翻译
videocaptioner subtitle raw.srt --no-translate --api-key $OPENAI_API_KEY -o optimized.srt
```

### 4. 全流程 + 精美样式

```bash
# 动漫风（暖色文字 + 橙描边）
videocaptioner process video.mp4 --asr bijian --translator bing --to ja \
  --subtitle-mode hard --style anime --quality high -o output_ja.mp4

# 现代圆角背景
videocaptioner process video.mp4 --asr bijian --translator google --to ko \
  --subtitle-mode hard --render-mode rounded -o output_ko.mp4

# 自定义颜色（白字红描边），画质 ultra
videocaptioner process video.mp4 --asr bijian --translator bing --to en \
  --subtitle-mode hard --quality ultra \
  --style-override '{"outline_color": "#ff0000", "primary_color": "#ffffff"}' -o output_en.mp4
```

### 5. 只要字幕文件，不合成视频

```bash
videocaptioner process video.mp4 --asr bijian --translator bing --to en \
  --format ass --no-synthesize -o ./output/
```

### 6. 分步执行（转写 → 翻译 → 合成）

```bash
videocaptioner transcribe video.mp4 --asr bijian -o video.srt
videocaptioner subtitle video.srt --translator bing --target-language en --layout source-above -o video_en.srt
videocaptioner synthesize video.mp4 -s video_en.srt --subtitle-mode hard \
  --render-mode rounded --quality high -o video_with_subs.mp4
```

### 7. 纯音频（自动跳过视频合成）

```bash
videocaptioner process podcast.mp3 --asr bijian --translator bing --to en -o ./output/
```

### 8. 其它语种转写（whisper-api）

```bash
videocaptioner transcribe french_video.mp4 --asr whisper-api \
  --whisper-api-key $OPENAI_API_KEY --language fr -o french.srt
```

### 9. 下载在线视频后配字幕

```bash
videocaptioner download "https://www.bilibili.com/video/BVxxxx" -o ./videos/
videocaptioner process ./videos/xxx.mp4 --asr bijian --translator bing --to zh-Hans -o out.mp4
```

### 10. 配音（TTS / 音色克隆）

```bash
videocaptioner dub video_en.srt --video video.mp4 --preset anna --timing balanced \
  --audio-mode mix --tts-api-key $TTS_API_KEY -o dubbed.mp4
```

配音能力参数较多（音色预设、说话人映射、克隆参考音频、时长适配），用前先看
@references/cli-reference.md 或 `videocaptioner dub --help`。

## 命令速查

| 命令 | 用途 |
| --- | --- |
| `transcribe` | 音视频 → 字幕。引擎：`bijian`(免费) `jianying`(免费) `whisper-api` `whisper-cpp` |
| `subtitle` | 润色（LLM）和/或翻译（LLM/Bing/Google）字幕文件 |
| `synthesize` | 把字幕烧进视频或封装为软字幕轨 |
| `process` | 全流程：转写 → 润色 → 翻译 → 合成 |
| `dub` | 用字幕生成配音音视频（TTS、音色克隆） |
| `download` | 下载在线视频（YouTube、Bilibili 等） |
| `config` | 配置管理：`show` `set` `get` `path` `init` `edit` |
| `style` | 列出全部字幕样式预设及其参数 |
| `doctor` | 诊断依赖与配置 |
| `gui` | 启动桌面应用 |

## 三个容易踩的坑

1. **`process` 的目标语言参数是 `--to`**，不是 `--target-language`。
   后者在 `process` 里是隐藏别名（能用但不显示），而 `subtitle` 命令里 `--target-language` 才是正式参数。
   拿不准就按命令分别记：`process` 用 `--to`，`subtitle` 用 `--target-language`。
2. **`subtitle` 默认会润色 + 重新断句，但默认不翻译**。
   想只翻译不改断句，加 `--no-optimize --no-split`；想只润色，加 `--no-translate`。
3. **`process` 默认 `--subtitle-mode soft`、`--quality medium`**。
   要烧进画面必须显式写 `--subtitle-mode hard`，否则只是封装一条可开关的字幕轨（画质损失更小，但平台会压掉）。

## 样式要点

- 样式参数**只在 `--subtitle-mode hard` 下生效**，软字幕由播放器决定外观。
- **ASS 模式**（默认）：`default` 白字黑描边、`anime` 暖色橙描边、`vertical` 竖屏
- **Rounded 模式**（`--render-mode rounded`）：圆角半透明底块，现代风格
- 自定义用 `--style-override '{"字段": 值}'`，字段清单跑 `videocaptioner style` 看
- 自定义字体用 `--font-file ./NotoSansSC.ttf`

## 交付前自检

1. `ffprobe` 比对成片与原片时长是否一致
2. 抽查开头、中间、结尾各 2 条：字幕与口型是否同步（误差 < 0.3 秒）
3. 硬字幕模式下确认字幕未被裁切（竖屏视频尤其注意 `margin_bottom`）
4. 双语模式下确认上下顺序符合用户预期（`--layout`）
5. 把产物路径、使用的语言对、样式参数一起告诉用户

## 排错

| 退出码 | 含义 | 处理 |
| --- | --- | --- |
| 0 | 成功 | `-q` 模式下 stdout 只输出结果路径 |
| 1 | 一般错误 | 看 stderr 首行 |
| 2 | 参数错误 / 缺配置 | `--help` 核对参数，或 `config show` 检查配置 |
| 3 | 文件不存在 | 校验输入路径 |
| 4 | 依赖缺失 | 跑 `videocaptioner doctor`，按提示装 ffmpeg/yt-dlp |
| 5 | 运行时错误 | 多为 API 失败，检查 key 与网络 |

- `pip install` 报 `Requires-Python` → 换 3.10–3.12 解释器并建 venv（见安装章节）
- `pip` 报 `Could not find a suitable TLS CA certificate bundle` → 本机 pip 证书配置指向了不存在的文件。
  临时绕过：`--cert <certifi 的 cacert.pem>` 并设 `PIP_CERT=<同一路径>`（子进程构建依赖时也要用）；
  根治：修正 `pip.ini` 里的 `cert=` 一项
- 装依赖时卡在下载 → 换镜像源 `-i https://pypi.tuna.tsinghua.edu.cn/simple`
- 转写只有中英文能用免费引擎，其它语种必须 `whisper-api` / `whisper-cpp`
- 中文显示为方块 → `--font-file` 指定中文字体
