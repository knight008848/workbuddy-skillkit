#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
asr.py — 本地 Whisper 转写（复用 VideoCaptioner 已下载的模型）

为什么单独做这一层：videocaptioner 命令行的 faster-whisper 引擎把 model_dir 写死成 None
也不传可执行路径，命令行跑不起来；但它 GUI 自带的 faster-whisper-xxl.exe 是独立程序，
可以直接调用。优势是本地推理、无网络依赖、带词级置信度。

用法：
    python scripts/asr.py doctor                      # 探测可执行程序与模型
    python scripts/asr.py run in.mp4 -o work/asr      # 转写，产出 srt + json + 低置信报告
    python scripts/asr.py run in.mp4 -o work/asr --language en --hotwords "Hogwarts,Wizarding World"
    python scripts/asr.py lowconf work/asr/in.json    # 单独重出低置信报告

退出码：0 成功 / 3 输入有问题 / 4 依赖缺失
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_MODEL = "large-v3-turbo"
DEFAULT_LOWCONF = 0.70
DEFAULT_TIMEOUT = 3600

# 短功能词的置信度天然偏低（"It was a joy" 的 It 只有 0.33），报出来只会淹没真问题。
# 这些词只有低到离谱（<0.3）时才值得看一眼。
FUNCTION_WORDS = {
    "a", "an", "the", "it", "its", "is", "was", "were", "be", "been", "am", "are",
    "at", "that", "this", "these", "those", "and", "or", "but", "to", "of", "in",
    "on", "for", "with", "you", "i", "we", "they", "he", "she", "my", "your", "his",
    "her", "their", "our", "us", "me", "him", "them", "do", "does", "did", "not",
    "so", "if", "as", "by", "from", "just", "all", "up", "out", "what", "when",
    "who", "how", "why", "then", "than", "too", "very", "can", "could", "would",
    "should", "will", "have", "has", "had", "there", "here", "now", "some", "any",
}


# ------------------------------------------------------------------ 依赖探测

def _gui_root():
    """VideoCaptioner GUI 的默认安装位置（Windows 用 LOCALAPPDATA）。"""
    local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "VideoCaptioner"


def find_exe(explicit=None):
    """按 显式指定 → 环境变量 → GUI 默认路径 → PATH 的顺序找 faster-whisper-xxl。"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env_exe = os.environ.get("VC_XXL_EXE")
    if env_exe:
        candidates.append(Path(env_exe))

    gui = _gui_root()
    candidates.append(gui / "resource" / "bin" / "Faster-Whisper-XXL" / "faster-whisper-xxl.exe")
    candidates.append(gui / "resource" / "bin" / "Faster-Whisper-XXL" / "faster-whisper-xxl")

    for name in ("faster-whisper-xxl", "faster-whisper-xxl.exe"):
        hit = shutil.which(name)
        if hit:
            candidates.append(Path(hit))

    for c in candidates:
        if c.is_file():
            return c
    return None


def find_model_root(explicit=None):
    """找「放着 faster-whisper-* 子目录」的那个父目录。"""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    env_dir = os.environ.get("VC_MODEL_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    candidates.append(_gui_root() / "AppData" / "models")
    candidates.append(Path.home() / "vc-models")

    for c in candidates:
        if c.is_dir() and any(c.glob("faster-whisper-*")):
            return c
    return None


def list_models(root):
    """列出 model.bin 完整的模型，返回 (model_name, 字节数)。"""
    out = []
    if not root:
        return out
    for d in sorted(root.glob("faster-whisper-*")):
        bin_path = d / "model.bin"
        if bin_path.is_file():
            name = d.name[len("faster-whisper-"):]
            out.append((name, bin_path.stat().st_size))
    return out


def pick_model(root, wanted):
    """优先用 wanted；不存在则认为该机器上有什么用什么。"""
    available = [n for n, _ in list_models(root)]
    if wanted in available:
        return wanted
    return available[0] if available else None


# ------------------------------------------------------------------ 转写

def run_cmd(cmd, timeout=DEFAULT_TIMEOUT):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 1, "", "timeout")
    except Exception as e:  # noqa: BLE001
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def cmd_doctor(args):
    exe = find_exe(args.exe)
    root = find_model_root(args.model_dir)
    models = list_models(root)

    print("faster-whisper 本地转写体检")
    print("-" * 46)
    if exe:
        print(f"[ok]   可执行程序  {exe}")
    else:
        print("[fail] 可执行程序  未找到")
        print("       安装 VideoCaptioner 桌面版（自带该程序），")
        print("       或下载 Faster-Whisper-XXL 后设 VC_XXL_EXE 指向它")

    if root:
        print(f"[ok]   模型根目录  {root}")
    else:
        print("[fail] 模型根目录  未找到（设 VC_MODEL_DIR，或先用 GUI 下载一次模型）")

    if models:
        print(f"[ok]   可用模型    {len(models)} 个")
        for name, size in models:
            print(f"         - {name:<16} {size / 2**30:.2f} GB")
    elif root:
        print("[fail] 可用模型    目录里没有完整的 faster-whisper-*（缺 model.bin）")

    ok = bool(exe and root and models)
    print("-" * 46)
    print("结论：" + ("可以本地转写" if ok else "本地转写不可用，需降级到 bijian"))
    return 0 if ok else 4


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_noise(word, prob):
    """功能词报低分是常态，不算可疑；只有低到离谱才留。"""
    clean = word.strip().strip(",.!?;:'\"“”‘’()[]—-").lower()
    if clean in FUNCTION_WORDS:
        return prob >= 0.30
    return False


def build_lowconf(data, threshold, limit=20):
    """把词级低置信片段组织成给模型看的报告：最可疑的词排在前面。"""
    rows = []
    for seg in data.get("segments", []):
        words = seg.get("words") or []
        low = [w for w in words
               if w.get("probability", 1.0) < threshold
               and not _is_noise(w.get("word", ""), w.get("probability", 1.0))]
        if not low:
            continue
        rows.append((min(w.get("probability", 1.0) for w in low), seg, low))

    if not rows:
        return ""
    rows.sort(key=lambda r: r[0])
    rows = rows[:limit]

    lines = []
    for worst, seg, low in rows:
        start = seg.get("start", 0)
        lines.append(f"[{start:>7.2f}s] {seg.get('text', '').strip()}")
        for w in sorted(low, key=lambda x: x.get("probability", 1.0)):
            lines.append(f"          可疑：{w.get('word', '').strip():<14} p={w.get('probability', 0):.2f}"
                         f"  @{w.get('start', 0):.2f}s")
    return "\n".join(lines)


def cmd_lowconf(args):
    data = _read_json(Path(args.json))
    report = build_lowconf(data, args.threshold)
    segs = data.get("segments", [])
    total = sum(len(s.get("words") or []) for s in segs)
    low = sum(1 for s in segs for w in (s.get("words") or [])
              if w.get("probability", 1.0) < args.threshold
              and not _is_noise(w.get("word", ""), w.get("probability", 1.0)))

    print(f"低置信词审计（阈值 {args.threshold}）：{low}/{total} 个词")
    if low == 0:
        print("没有低于阈值的词——这一片识别得很稳，不需要逐条核对。")
        return 0
    print("这些词是「可疑」不是「一定错」，结合上下文判断，拿不准就保留原样。\n")
    print(report)
    return 0


def cmd_run(args):
    exe = find_exe(args.exe)
    root = find_model_root(args.model_dir)
    if not exe or not root:
        print("本地转写不可用（缺可执行程序或模型）。先跑：python scripts/asr.py doctor",
              file=sys.stderr)
        return 4

    model = pick_model(root, args.model)
    if not model:
        print(f"模型目录 {root} 里没有完整的 faster-whisper-* 模型", file=sys.stderr)
        return 4

    src = Path(args.input)
    if not src.is_file():
        print(f"输入文件不存在：{src}", file=sys.stderr)
        return 3

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.stem or src.stem
    for stale in (out_dir / f"{stem}.srt", out_dir / f"{stem}.json"):
        if stale.exists():
            stale.unlink()

    cmd = [
        str(exe), str(src.resolve()),
        "--model", model,
        "--model_dir", str(root.resolve()),
        "--output_dir", str(out_dir.resolve()),
        "--output_format", "srt", "json",
        # 按句切分：默认按停顿切，会出 5–6 秒一条的巨块，无法直接做字幕
        "--sentence",
        "--word_timestamps", "True",
        "--vad_filter", "True",
    ]
    if args.language and args.language != "auto":
        cmd += ["--language", args.language]
    if args.hotwords:
        cmd += ["--hotwords", args.hotwords]
    if args.device:
        cmd += ["--device", args.device]

    print(f"转写：{src.name}")
    print(f"  模型 {model} / 程序 {exe.name} / 输出 {out_dir}")
    proc = run_cmd(cmd)

    combined = (proc.stdout or "") + (proc.stderr or "")
    produced = out_dir / f"{src.stem}.srt"
    # 这个程序收尾时偶发崩溃（0xC0000409），但文件已经写完，不能据此判定失败
    if proc.returncode != 0 and not produced.is_file():
        print(combined[-2000:], file=sys.stderr)
        print(f"转写失败（退出码 {proc.returncode}）", file=sys.stderr)
        return 1
    if proc.returncode != 0:
        print(f"  提示：程序退出码 {proc.returncode}（收尾崩溃，文件已完整写出，可忽略）")

    srt = out_dir / f"{src.stem}.srt"
    js = out_dir / f"{src.stem}.json"
    if not srt.is_file() or not js.is_file():
        print(combined[-2000:], file=sys.stderr)
        print("程序跑完但没找到输出文件，检查 --output_format 与输出目录权限", file=sys.stderr)
        return 1

    # 输出名带上「｜」这类字符会污染后续路径，允许改名成 src.srt
    if args.stem and args.stem != src.stem:
        for old in (srt, js):
            old.replace(out_dir / f"{args.stem}{old.suffix}")
        srt = out_dir / f"{args.stem}.srt"
        js = out_dir / f"{args.stem}.json"

    dev = "CUDA" if "running on: CUDA" in combined else "CPU"
    print(f"  算力 {dev}")

    data = _read_json(js)
    cues = srt.read_text(encoding="utf-8", errors="replace").count(" --> ")
    # json 的 segments 是原始停顿块，条数以带 --sentence 的 srt 为准
    print(f"  完成：{cues} 条 → {srt.name}")

    report = build_lowconf(data, args.lowconf)
    if report:
        report_path = out_dir / f"{stem}.lowconf.txt"
        report_path.write_text(report, encoding="utf-8")
        low = sum(1 for s in data.get("segments", []) for w in (s.get("words") or [])
                  if w.get("probability", 1.0) < args.lowconf
                  and not _is_noise(w.get("word", ""), w.get("probability", 1.0)))
        print(f"  低置信：{low} 个词（阈值 {args.lowconf}）→ {report_path.name}")
        print("  下一步：把这份报告里的可疑词结合上下文改掉，再进 segments.py extract")
    else:
        print("  低置信：无，识别稳定")

    return 0


def main():
    ap = argparse.ArgumentParser(description="本地 Whisper 转写（复用 VideoCaptioner 模型）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor", help="探测可执行程序与模型")
    d.add_argument("--exe")
    d.add_argument("--model-dir")
    d.set_defaults(func=cmd_doctor)

    r = sub.add_parser("run", help="转写并产出低置信报告")
    r.add_argument("input")
    r.add_argument("-o", "--out-dir", default="work/asr")
    r.add_argument("--stem", help="输出文件名（不含扩展名），默认沿用输入文件名")
    r.add_argument("--language", default="auto")
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--model-dir")
    r.add_argument("--exe")
    r.add_argument("--device", help="cpu / cuda，留空让程序自己选")
    r.add_argument("--hotwords", help="逗号分隔的专有名词，能明显减少人名识别错")
    r.add_argument("--lowconf", type=float, default=DEFAULT_LOWCONF)
    r.set_defaults(func=cmd_run)

    l = sub.add_parser("lowconf", help="从已有 json 重出低置信报告")
    l.add_argument("json")
    l.add_argument("--threshold", type=float, default=DEFAULT_LOWCONF)
    l.set_defaults(func=cmd_lowconf)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
