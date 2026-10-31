# videocaptioner CLI 参考（v1.4.2 核对）

本文件是 SKILL.md 的展开细节。只在需要精确参数时读取，不必一开始就加载。

## 1. 命令与关键参数

### transcribe — 音视频转字幕

| 参数 | 说明 |
| --- | --- |
| `input` | 音视频路径 |
| `--asr` | `bijian`(默认，免费) `jianying`(免费) `whisper-api` `whisper-cpp` |
| `--language` | 源语言 ISO 639-1，默认 `auto` |
| `--word-timestamps` | 输出词级时间戳（供后续断句用） |
| `--whisper-api-key` / `--whisper-api-base` / `--whisper-model` | whisper-api 专有 |
| `-o` / `--format` | 输出路径；格式 `srt`(默认) `ass` `txt` `json` |

免费引擎（bijian / jianying）**仅支持中文和英文**，其它语种必须走 whisper 系。

### subtitle — 润色 / 翻译字幕

默认行为：**润色开、重新断句开、翻译关**。

| 参数 | 说明 |
| --- | --- |
| `--no-optimize` | 跳过 LLM 润色 |
| `--no-split` | 跳过重新断句 |
| `--no-translate` | 跳过翻译 |
| `--translator` | `llm` `bing`(默认) `google`；后两者免费 |
| `--target-language` | 目标语言 BCP 47，默认 `zh-Hans` |
| `--reflect` | 反思式翻译，仅 LLM |
| `--layout` | `target-above`(默认) `source-above` `target-only` `source-only` |
| `--max-cjk` / `--max-english` | 每行最大中文字数（默认 18）/ 英文词数（默认 12） |
| `--prompt` | 自定义润色或翻译提示词 |
| `--thread-num` / `--batch-size` | 并发线程（默认 4）/ 批大小（默认 20） |

### process — 全流程

转写 → 润色 → 断句 → 翻译 → 合成，串成一条命令。

| 参数 | 说明 |
| --- | --- |
| `--to` | **目标语言（正式参数）**；`--target-language` 是隐藏别名 |
| `--asr` `--language` | 同 transcribe |
| `--translator` `--reflect` | 同 subtitle |
| `--no-optimize` `--no-translate` `--no-split` `--no-synthesize` | 各环节跳过开关 |
| `--quality` | `ultra` `high` `medium`(默认) `low` |
| `--subtitle-mode` | `soft`(默认) `hard` |
| `--layout` | 同上，默认 `target-above` |
| `--render-mode` `--style` `--style-override` `--font-file` | 样式，仅 hard 生效 |
| `--format` | 字幕输出格式 |
| `--dub` / `--dub-only` | 顺带生成配音 / 只输出配音结果 |

### synthesize — 字幕合成

| 参数 | 说明 |
| --- | --- |
| `video` + `-s/--subtitle`（必填） | 输入视频与字幕 |
| `--subtitle-mode` | `soft` 封装字幕轨 / `hard` 烧进画面 |
| `--quality` | 视频质量档位 |
| `--layout` | 双语排布方式 |
| 样式参数 | 仅 hard 生效 |

### dub — 配音

| 参数 | 说明 |
| --- | --- |
| `subtitle` + `--video` | 字幕与可选视频 |
| `--preset` | 音色预设（`videocaptioner dub --help` 列出） |
| `--voice` | 默认音色，如 anna、alex、benjamin、Kore |
| `--speak` | 双语字幕念哪一行：`auto` `first` `second` |
| `--timing` | `balanced` `strict` `natural` `none` |
| `--adapt-length` | 时间槽放不下时压缩文案 |
| `--audio-mode` | 原声处理：`replace` `mix` `duck` |
| `--speaker-voice NAME=VOICE` | 说话人 → 音色，可重复 |
| `--speaker-clone NAME=AUDIO\|TEXT` | 说话人 → 克隆参考音频，可重复 |
| `--clone-audio` / `--clone-text` | 默认克隆参考 |
| `--tts-api-key` | TTS key（也可 `config set dubbing.api_key`） |

### download / config / style / doctor / gui

- `download <url> -o <dir>`：下载在线视频，依赖 yt-dlp
- `config show|set|get|path|init|edit`：`set` 用点号键，如 `config set llm.api_key sk-xxx`；
  `init --profile basic|dubbing --non-interactive` 可非交互生成配置
- `style`：列出全部样式预设及字段
- `doctor [--json] [--check-api]`：依赖体检，有 error 时退出码 4
- `gui`：启动桌面应用

## 2. 样式系统

两种渲染模式：

**ASS 模式（默认）** — 描边/阴影风格

- 预设：`default`（白字黑描边）、`anime`（暖色 + 橙描边）、`vertical`（竖屏专用）
- 可调字段：`font_name` `font_size` `primary_color` `outline_color` `outline_width` `bold` `spacing` `margin_bottom`

**Rounded 模式** — 现代圆角背景块

- 预设：`rounded`（半透明底 + 深色字）
- 可调字段：`font_name` `font_size` `text_color` `bg_color`(`#rrggbbaa`) `corner_radius` `padding_h` `padding_v` `margin_bottom`

写法：

```bash
--style-override '{"text_color": "#ffffff", "bg_color": "#000000cc", "corner_radius": 10, "font_size": 36}'
```

样式参数**只在 `--subtitle-mode hard` 下有意义**，软字幕由播放器渲染。

## 3. 支持的目标语言（BCP 47，共 38 个）

`zh-Hans` `zh-Hant` `en` `en-US` `en-GB` `ja` `ko` `yue` `th` `vi` `id` `ms` `tl`
`fr` `de` `es` `es-419` `ru` `pt` `pt-BR` `pt-PT` `it` `nl` `pl` `tr`
`el` `cs` `sv` `da` `fi` `nb` `hu` `ro` `bg` `uk` `ar` `he` `fa`

不在表内的 code 会报 `Unknown target language` 并列出全部可用值。

## 4. 环境变量

| 变量 | 用途 |
| --- | --- |
| `OPENAI_API_KEY` | LLM key（润色 / 断句 / LLM 翻译） |
| `OPENAI_BASE_URL` | LLM 接口地址（兼容 OpenAI 协议的第三方服务） |

优先级：命令行参数 > 环境变量 > `config` 文件。

## 5. 退出码

| 码 | 常量 | 场景 |
| --- | --- | --- |
| 0 | SUCCESS | 成功 |
| 1 | GENERAL_ERROR | 未分类错误 |
| 2 | USAGE_ERROR | 参数非法、缺必需配置 |
| 3 | FILE_NOT_FOUND | 输入文件不存在 |
| 4 | DEPENDENCY_MISSING | ffmpeg / yt-dlp / 模型文件缺失 |
| 5 | RUNTIME_ERROR | API 失败、处理中断 |

脚本化时用 `-q`，stdout 只有结果路径，便于 `$(videocaptioner ... -q)` 捕获。
