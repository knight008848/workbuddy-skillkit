# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循语义化版本。
发布前请确认本文件最新条目的版本号与 `SKILL.md` 的 `version` 一致（`build/pack.py` 会核对）。

## [未发布]

## [1.1.2] - 2026-10-31

### 修复

- `segments.py merge`：`__MERGE_PREV__` 现在会把被并入条目的**原文**一并接到上一条，
  此前只并时间窗，导致中英不对称（实测中文有「阿门」、英文只剩 `We'll be seeing you soon.`）。
  四种版式（target-above / source-above / target-only / source-only）均已回归

### 文档

- 低置信报告一节补「切出片段 + `--hotwords` 复听」的做法：
  实测把 `O'Glorious Weeda`（p=0.48）纠正为 `oh glorious leader`，代价只有几秒
- 断句一节补「译文要自己写全」，说明脚本不会替你补被合并的语义

## [1.1.1] - 2026-10-31

### 变更

- 吸纳 `videocaptioner` CLI 命令全表（`references/videocaptioner-cli.md`），
  技能自此自包含，不再依赖外部技能取参数
- 移除配套的 `videocaptioner` 技能：它只是 CLI 的包装，不单独上架

## [1.1.0] - 2026-10-31

### 新增

- `scripts/asr.py`：本地 Whisper 转写入口，三个子命令
  - `doctor` 探测可执行程序与模型，缺什么就说缺什么
  - `run` 转写并同时产出 srt、json、低置信报告
  - `lowconf` 对已有 json 重出报告，便于调阈值
- 低置信报告：按词级 `probability` 挑出可疑词，供纠错时优先复核

### 变更

- 转写主引擎由 `bijian` 免费接口改为**本地 faster-whisper-large-v3-turbo 优先**，
  免费引擎降为兜底。实测 48 秒片子 2.4 秒跑完（CUDA，20× 实时）
- 转写步骤改为 `asr.py run`，不再直调 `videocaptioner transcribe`
- `description` 补充「本地 Whisper 优先，免费引擎兜底」

### 修复

- 免费 ASR 在背景音乐重、专有名词多的片段上严重失真
  （`custo old brought his home` → 实际是 `Hogwarts is home`）
- `--sentence` 只作用于 srt、json 仍是原始停顿块的问题：文档中明确标注

### 已知限制

- 段级 `avg_logprob` 无区分度（实测全为 -0.20），只有词级 `probability` 可用
- 段级置信度无法从 videocaptioner CLI 取到，必须走 `asr.py`
- `faster-whisper-xxl.exe` 写完文件后偶发以 3221226505 崩溃退出，脚本按「文件存在即成功」处理

## [1.0.0] - 2026-10-31

### 新增

- 首个版本，三段式流程：`preflight.py` 环境体检 → `segments.py` 翻译交接 → `verify.py` 交付验收
- `segments.py` 四个子命令：`extract` / `merge` / `concat` / `audit`
- `install_styles.py`：安装 4 套字幕预设到 VideoCaptioner 资源目录
- `templates/styles/`：双鱼版式与 4 个预设（ass / rounded 两种渲染模式）
- `references/recipes.md`、`references/quality.md`
- 强制 `--layout source-above`，避免中文在下
