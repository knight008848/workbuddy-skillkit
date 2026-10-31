# 变更记录

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [未发布]

## [1.0.0] - 2026-10-31

### 新增

- 首个版本：基于 videocaptioner CLI 1.4.2 的字幕工具流程
- `references/cli-reference.md`：`transcribe` / `synthesize` / `process` / `subtitle` / `dub` / `doctor` / `style` 全命令表
- 版式陷阱记录：`merge` 默认译文在第一行，`synthesize` 把第一行当原文，
  故烧录须显式 `--layout source-above`

### 已知限制

- 依赖 PyPI 包 `videocaptioner`，要求 Python 3.10–3.12（3.13 被作者的上限卡住）
- 免费翻译（Bing / Google）在受限网络下会静默失败且退出码仍为 0，
  正式流程请用模型自译（bilingual-subtitle 已按此设计）
