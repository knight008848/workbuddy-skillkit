---
name: bilingual-subtitle
display_name: 双语字幕成片
display_name_en: Bilingual Subtitle
description: '把外语视频做成中英（或任意语言对）双语字幕成片的流程技能：先转写（本地 Whisper 优先，免费引擎兜底）、翻译、按双语版式烧录或封装，再用内置脚本做前置体检和交付验收。适用于「给英文视频加中文字幕」「做成中英双语对照」「两只字幕一上一下」「字幕翻译后压进视频」「检查字幕有没有溢出/不同步」这类需求。This skill should be used when the user wants a bilingual subtitle video: transcribe, translate into two languages shown together, burn in or mux, and verify the result. 触发词：双语字幕、中英双语、双语对照、字幕成片、加中文字幕、英文字幕翻译、硬字幕、软字幕、bilingual subtitles。'
description_zh: '外语视频一键出双语字幕成片：转写、翻译、双语版式烧录/封装，附带前置体检与交付验收脚本。'
description_en: 'Produce bilingual subtitle videos end to end: transcribe, translate, lay out two languages, burn in or mux, with preflight and acceptance checks.'
examples_zh:
  - '把这个英文预告片做成中英双语字幕，压成 mp4'
  - '英文字幕翻成中文，做成中文在上英文在下的对照字幕'
  - '帮我检查这份双语字幕有没有溢出、不同步的问题'
examples_en:
  - 'Make a Chinese-English bilingual subtitled mp4 from this English trailer'
  - 'Translate the English subtitles and lay them out with Chinese above English'
  - 'Check this bilingual subtitle file for overflow and sync issues'
version: 1.1.0
author: "个人开发者"
license: MIT
allowed-tools: Bash, Read, Write
agent_created: true
---

# 双语字幕成片

本技能是**流程与验收层**：转写用本地 Whisper（`asr.py`）或引擎自带接口，  
合成用 `videocaptioner`，翻译环节由模型自己完成，不调用在线翻译接口。

本技能负责四件事：跑之前检查环境、转写后把字幕拆成可安全翻译的条目、  
按双语版式烧录、跑完判定合格。引擎本身的命令全表见 videocaptioner 技能。

**四条主线**：`preflight.py`（体检）→ `asr.py`（转写）→ `segments.py`（翻译交接）  
→ `verify.py`（验收）。

## 一、先体检，再动手

```bash
python scripts/preflight.py "<视频路径>"
```

它会一次问清：文件在不在、有没有音轨、ffmpeg 与 videocaptioner 装没装、  
样式预设是否齐全，并直接打印出可直接照抄的 6 步命令。**不要跳过这步**——双语流程里  
最贵的浪费是跑到合成阶段才发现缺 ffmpeg 或样式预设。

退出码：`0` 可开工 / `3` 输入有问题 / `4` 依赖缺失。

转写引擎单独查一条：`python scripts/asr.py doctor`。它只看两件事——xxl 程序在不在、  
模型下没下过。`preflight.py` 查的是合成侧，两者互补。

## 二、环境准备（顺序照做，这几步都有坑）

```bash
# 1. 必须 Python 3.10–3.12，3.13 装不上（Requires-Python: <3.13,>=3.10）
python3.12 -m venv .venv-vc
.venv-vc/Scripts/python -m pip install videocaptioner

# 2. 1.4.2 有打包 bug：声明依赖 httpx2，代码却 import httpx，必装这一个
.venv-vc/Scripts/python -m pip install httpx

# 3. ffmpeg（二选一）
winget install --id Gyan.FFmpeg -e            # 常规
pip install imageio-ffmpeg                     # GitHub 被墙/太慢时的备用，5 秒到手
#   备用方案拿到的二进制在 site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-*.exe，
#   复制成 ffmpeg.exe 放进任意 PATH 目录即可

# 4. 样式预设（pip 包不自带，缺了 synthesize 直接报 Style preset not found）
python scripts/install_styles.py
```

`pip` 报 `Could not find a suitable TLS CA certificate bundle` 时，用 `--cert` 指定  
pip 自带的 certifi 证书，并同时设 `PIP_CERT`（构建子进程要用）：  
`--cert <venv>/Lib/site-packages/pip/_vendor/certifi/cacert.pem`。

## 三、判断走哪条路

| 用户手上有什么         | 走法                                        |
| --------------- | ----------------------------------------- |
| 只有视频/音频         | 转写 → 模型翻译 → 烧录（第四节全流程）                    |
| 已有字幕文件（srt/ass） | 跳过转写，从 `segments.py extract` 开始，**时间轴不漂** |
| 只想要字幕文件         | 到第 6 步为止，不做 `synthesize`                  |
| 要平台可开关的字幕轨      | 第 7 步把 `--subtitle-mode hard` 换成 `soft`   |

## 四、标准流程（外语视频 → 中文字幕成片）

翻译**不调用任何在线翻译接口**，由模型自己翻。原因见第八节。

```bash
# 1. 体检：缺依赖会直接告诉你装什么，并打印推荐命令
python scripts/preflight.py input.mp4

# 2. 转写：只出原文，不翻译。本地模型优先（理由见下节）
python scripts/asr.py doctor                                  # 先确认模型在不在
python scripts/asr.py run input.mp4 -o work/asr --language en --stem src
#   本地不可用时降级：videocaptioner transcribe input.mp4 --asr bijian -o work/asr/src.srt

# 3. 拆成待译条目（时间码由脚本保管，模型只碰文字）
python scripts/segments.py extract work/asr/src.srt -o work/seg.json

# 4. 断句体检：直接列出哪几条该拆、哪几条该并，不用肉眼过几百条
python scripts/segments.py audit work/seg.json

# 5. 模型读 work/seg.json，写 work/dst.json
#    格式：{"1": "译文"}  或  {"1": {"dst": "译文", "src": "纠正后的原文"}}
#    听到明显错词（人名、术语）就在这一步顺手改 src，别只填译文

# 6. 合回双语 srt（默认译文在上，中文行会被检查行宽）
#    --normalize-en 修 ASR 的全小写、缺句末标点、i 未大写
python scripts/segments.py merge work/seg.json --dst work/dst.json \
  -o subtitles/bilingual.srt --normalize-en

# 7. 烧录。注意这里是 source-above，理由见第六节
videocaptioner synthesize input.mp4 -s subtitles/bilingual.srt \
  --subtitle-mode hard --quality high --style default --layout source-above \
  -o output.mp4

# 8. 验收
python scripts/verify.py --subtitle subtitles/bilingual.srt \
  --video output.mp4 --source input.mp4 --bilingual
```

**为什么第 3 步和第 6 步要拆开**：模型全程不碰时间码。长视频几百条，手改 srt  
抄错一个时间码，那一段之后字幕整体漂移，且极难定位。`segments.py` 只让模型产出  
「编号 → 译文」的对照表，时间码由脚本原样搬运，错误面从几百行 srt 缩到几十行译文。

`merge` 会硬性检查「每条都有译文」，缺一条直接退出码 2，不静默跳过——  
空条会在成片上留下没有字幕的空白段。

第 2 步的字幕文件不要删。**没有它就没法返工**：重跑一遍 ASR 几分钟又没了，  
而改一行译文只要几秒。

### 转写引擎：优先本地 Whisper

按顺序尝试，能用第一个就别用第二个：

| 引擎                    | 命令                                       | 前提                    | 特点                     |
| --------------------- | ---------------------------------------- | --------------------- | ---------------------- |
| 本地 faster-whisper（首选） | `scripts/asr.py run`                     | 装过 VideoCaptioner 桌面版 | 有 CUDA 时 20× 实时，带词级置信度 |
| bijian                | `videocaptioner transcribe --asr bijian` | 无                     | 免费、零依赖，错词多             |
| whisper-api           | `--asr whisper-api --whisper-api-base …` | OpenAI 兼容 key         | 境外服务，国内多数不通            |

**为什么绕开 `--asr faster-whisper`**：videocaptioner 命令行把 `faster_whisper_model_dir`  
写死成 `None`、也不传可执行程序路径（`cli/commands/transcribe.py:105`），这条路在 CLI 里是断的。  
但 GUI 自带的 `faster-whisper-xxl.exe` 是独立程序、模型也已经在本地，`asr.py` 直接驱动它。

探测顺序（都在 `asr.py doctor` 里能看到结果）：

| 目标  | 顺序                                                                                               |
| --- | ------------------------------------------------------------------------------------------------ |
| 程序  | `--exe` → `VC_XXL_EXE` → `%LOCALAPPDATA%\VideoCaptioner\resource\bin\Faster-Whisper-XXL\` → PATH |
| 模型  | `--model-dir` → `VC_MODEL_DIR` → `%LOCALAPPDATA%\VideoCaptioner\AppData\models`                  |
| 模型名 | 默认 `large-v3-turbo`，本机没有就退到已有的那个                                                                 |

固定加的三组参数，每个都有代价：

| 参数                       | 不写会怎样                       |
| ------------------------ | --------------------------- |
| `--sentence`             | 按停顿切块，5–6 秒一条、一条塞三句，没法直接做字幕 |
| `--word_timestamps True` | 拿不到词级 `probability`，无法定位可疑词 |
| `--vad_filter True`      | 静音段触发幻觉，凭空多出整句              |

实测对照（同一段音频，三个引擎）：

| 引擎                | 同一句的识别结果                                |
| ----------------- | --------------------------------------- |
| bijian            | `this other machine of guious wida`     |
| WorkBuddy 内置      | `this other machine, Oh, gloorious wia` |
| 本地 large-v3-turbo | `this other machine, O'Glorious Weeda?` |

另一部更明显：bijian 的 `their own tense custo old brought his home`，  
本地模型给出 `Hogwarts is home. It's about outsiders`——听的就是这句。

**但本地模型照样会错**，只是错得更像人话（`my plan`→`my bland`，`what`→`where`）。  
所以转写完必须看低置信报告，别把它当权威。

### 低置信报告怎么用

`run` 顺手产出 `src.lowconf.txt`：把 `probability < 0.7` 的词连同所在句一起列出。  
拿它当「该看哪几行」的索引，不用肉眼过全片。

- **段级 `avg_logprob` 别看**：实测每一段都是 `-0.20`，没有任何区分度，只有词级 `probability` 有用。
- 阈值 0.7 是权衡：`Weeda?(0.48)`、`where(0.70)` 抓得到；`bland(0.8+)` 抓不到。  
  抓到的不一定是错的（`Lord,` 0.66 就是对的），漏掉的也不一定对——**它是线索，不是判决**。
- 功能词（`it` / `at` / `the` …）已过滤：短词置信度天然偏低，不滤的话满屏噪声（实测 376 词里  
  会多出十几个纯噪声）。只有它们低到 `p<0.3` 才保留。
- 报告按「最可疑的句子」排序、最多 20 句，从上往下改就行，不用全改。
- 改的地方是 `dst.json` 的 `src` 字段，不要直接改 srt（见下节）。

### 断句：本地引擎已切好，仍需抽查

本地引擎带了 `--sentence`，实测一部 48 秒片子切成 13 条、每条 1.4–3.2 秒，直接可用。  
用 bijian 时没有这个待遇（按停顿切，常一条塞三句），要自己拆。

第 5 步写 `dst.json` 时把下面四种毛病一并修掉：

| 毛病      | 转写长这样                                         | 怎么写                                |
| ------- | --------------------------------------------- | ---------------------------------- |
| 两句挤一条   | `Get back to your unit . who clicks that way` | 用数组拆成两条                            |
| 长句超一屏   | 5 秒、40 个词的一句                                  | 同上，按语义拆 2–3 段                      |
| 碎片单独成条  | 一条只有一个 `and`，0.4 秒                            | `"__MERGE_PREV__"`，时间并入上一条         |
| 一句被切成两条 | 上条 `I'd like to`，下条 `but it's my plan`        | 上条写合并后的完整文本，下条标 `"__MERGE_PREV__"` |

```json
{
  "7": {"src": ["Get back to your unit.", "Who cliques that way?"],
        "dst": ["回你的小队去。", "谁这么拉帮结派的？"]},
  "5": "__MERGE_PREV__"
}
```

数组的长度就是拆分后的条数，`src` 与 `dst` **必须等长**，脚本按各段原文字数比例  
分配时间窗——原文长短与念出来耗时基本成正比，平均分会把短句拖长、长句挤短。  
拆出的段短于 0.4 秒会告警：通常说明这句不该拆，该并。

判据：**一条字幕停留 1–4 秒**，中文一行 ≤ 18 字，英文 ≤ 12 词。三条都满足才算断句合格。

纠错同理，在 `dst.json` 里改 `src`：拼写与术语（`hardboard`→`Hogwarts`、  
`cottage`→`courage`、`wisdom world`→`Wizarding World`）直接改；**听不出来又猜不准的  
不要编**，保留原样并在交付说明里标出来，让用户决定——编错了比留着更麻烦。

更多场景（术语表、竖屏、长视频分段、已有英文字幕）见 @references/recipes.md。

## 五、验收：把「看着还行」变成清单

```bash
python scripts/verify.py --subtitle out.srt --video out.mp4 --source in.mp4 --bilingual
```

硬性项（任一不过即不可交付）：双语条目占比 ≥ 90%、时长为正、时间轴无重叠、  
末条不越界、无乱码、成片与原片时长差 ≤ 0.5s。  
软性项（告警需人判断）：中文行宽 ≤ 18 字、英文行宽 ≤ 12 词、srt 带 BOM。

完整判据与「症状 → 修法」对照见 @references/quality.md。

## 六、烧录版式：最容易翻车的一处

`synthesize` 从 srt 读字幕时**只能靠位置猜**：第一行当原文（Default 样式，字号大），  
第二行当译文（Secondary，字号小）。而它的默认版式是「译文在上」。

所以合并与烧录两处填的 `--layout` 是**反的**：

| 环节                                     | 该填什么                    | 含义        |
| -------------------------------------- | ----------------------- | --------- |
| `segments.py merge`（默认 `target-above`） | 译文写在第一行、原文第二行           | 管「文件里谁在前」 |
| `synthesize`                           | `--layout source-above` | 管「画面上谁在上」 |

实测（videocaptioner 1.4.2）：merge 默认输出「中文第一行、英文第二行」，  
烧录时若漏掉 `--layout source-above`，画面会变成**英文在上、中文在下**。

一句话记法：**文件里中文在前，烧录就写 `source-above`**。

## 七、调样式

样式只在 `--subtitle-mode hard` 下生效，且**依赖 `scripts/install_styles.py` 装好的预设**。  
内置四个：`default`（通用横屏）、`vertical`（竖屏，底距 320）、`anime`（暖色橙描边）、  
`rounded`（圆角底块，需 `--render-mode rounded`）。

**字体字段在两种渲染模式下含义不同**，这是引擎里最隐蔽的一处：

| 模式                            | `font_name` 要写什么                           | 为什么                                                        |
| ----------------------------- | ------------------------------------------ | ---------------------------------------------------------- |
| `ass`（default/vertical/anime） | **字体族名**，如 `Microsoft YaHei`               | 名字被写进 ASS 的 Style 行，交给 libass 用 fontconfig 解析；写路径反而找不到     |
| `rounded` / PIL 渲染            | **字体文件绝对路径**，如 `C:/Windows/Fonts/msyh.ttc` | `ImageFont.truetype()` 把字符串当文件路径，写族名会 OSError 后一路 fallback |

`install_styles.py` 安装时会自动探测本机中文字体，只给 rounded 类预设注入路径，ass 类保持族名不动。

烧录日志里出现 `Cannot load font 'Microsoft YaHei'` + `All fallback fonts failed`  
**不代表字幕坏了**——这只说明 PIL 那一路没找到字体文件，而 ass 模式的实际渲染由 libass 完成。  
判断标准永远是抽一帧看画面，不要只看日志。

临时微调用 `--style-override`，字段见 `templates/styles/presets/*.json`：

```bash
--style-override '{"font_size": 58, "margin_bottom": 72, "outline_width": 3}'
```

混合两份预设时，改哪个字段就只写哪个，未写的沿用预设默认值。

## 八、交付

告诉用户四件事，不要只丢一个文件路径：

1. 成片路径 + 字幕文件路径
2. 语言对与版式（例如「中英对照，中文在上」）
3. 用的引擎和档位（例如「本地 large-v3-turbo 转写 + 模型翻译，画质 high」）
4. 验收结论（verify.py 是否通过、有无告警项）

## 九、为什么不用在线翻译接口

这是本技能的一个明确取舍，**不要改回去**。

`videocaptioner` 自带 `--translator bing` 和 `--translator google`，看起来最省事，  
但实测有三个问题，其中第三个是致命的：

1. **可用性没保证**。Bing 的鉴权接口直接 404，Google 走代理 502，换地区换时间结果都不一样。
2. **质量不可控**。影视台词里的双关、人名、语气词，机器翻译基本只能直译；  
   而字幕最忌讳「意思对但不像人说话」。
3. **失败时静默返回 0**。翻译挂了它照样退出码 0、照样产出文件，只是字幕里只剩一种语言。  
   如果没跑验收，会一路做到成片才发现，前面全白做。

改成模型翻译后：术语表、语气、断句、长度压缩都在一步里解决，还能顺手纠正 ASR 的识别错误，  
且不依赖任何外部服务是否存活。

代价是**长视频会占用较多上下文**。超过 300 条时按 @references/recipes.md 里的分段做法，  
每批 100～150 条处理，批次之间保持术语一致。

## 常见的坑（都是实测踩出来的）

| 坑           | 表现                                                               | 处理                                                                            |
| ----------- | ---------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 打包 bug      | `ModuleNotFoundError: No module named 'httpx'`                   | `pip install httpx`                                                           |
| 样式预设缺失      | `Style preset not found: 'default'`                              | `python scripts/install_styles.py`                                            |
| 版式反了        | 英文在上、中文在下                                                        | 烧录加 `--layout source-above`（见第六节）                                             |
| 译文缺失        | `merge` 退出码 2，列出缺的条目号                                            | 补齐 dst.json 再合并；这是故意的，不留空条                                                    |
| 时间码漂移       | 字幕整体提前/滞后                                                        | 别手改 srt 的时间码，一律走 `segments.py`                                                |
| 默认不烧录       | 出了软字幕轨                                                           | 显式 `--subtitle-mode hard`                                                     |
| 免费 ASR 语种限制 | 非中英文识别乱                                                          | 换 `--asr whisper-api`                                                         |
| 免费 ASR 错词   | 人名、术语识别错                                                         | 优先用 `scripts/asr.py run` 换本地模型；已在 dst.json 里就顺手给 `src` 纠正值                    |
| 本地程序收尾崩溃    | 退出码 `3221226505` / `0xC0000409`，但 srt 已写完                        | `asr.py` 已按「文件写出即成功」处理，看到这行提示可以忽略                                             |
| 本地模型条目数偏少   | srt 一条塞了三句                                                       | 检查 `--sentence` 是否被漏掉；它只作用于 srt，json 里仍是原始停顿块                                 |
| 找不到本地模型     | `doctor` 报模型未找到                                                  | 用 GUI 下载一次模型（设置里选 large-v3-turbo），或设 `VC_MODEL_DIR` 指向模型根目录                   |
| 字体加载失败      | 日志 `Cannot load font` / `All fallback fonts failed`              | 先抽帧看画面；ass 模式这条警告可忽略，rounded 模式必须换字体文件路径（见第七节）                                |
| 中文显示方块      | 画面里中文字符是空心方块                                                     | 该机没有中文字体，装一个或用 `--font-file` 指定 ttf                                           |
| 并发跑转写       | `sqlite3.OperationalError: attempt to write a readonly database` | videocaptioner 的缓存是单个 sqlite，**同一时刻只能跑一个实例**；批处理要串行排队                         |
| 在线 ASR 被拦   | `ConnectionResetError(10054)` 或指向 `*.biliapi.net` 的连接超时          | 免费引擎走必剪的在线接口，企业网关/沙箱/代理会拦；改走 `scripts/asr.py run`，本地跑不需要网络                    |
| 转写质量差       | 专有名词全错、句子断得莫名其妙                                                  | 免费引擎只适合草稿；重要交付用本地 large-v3-turbo，术语可加 `--hotwords "Hogwarts,Wizarding World"` |
| 英文行大小写乱     | 同一条字幕里 `i` 小写、句末无标点                                              | 只在 dst.json 里改 `src` 的条目会被规范化，没改的保留原样；交付前统一过一遍                                |
