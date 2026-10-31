#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preflight.py — 双语字幕任务的前置体检

在跑任何 videocaptioner 命令之前先跑这个，把「装没装、有没有音轨、该用什么参数」一次问清，
避免跑到一半才发现 ffmpeg 缺失或者视频根本没有声音。

用法：
    python scripts/preflight.py video.mp4
    python scripts/preflight.py video.mp4 --target zh-Hans --mode soft --json

退出码：0 可以开工 / 3 输入文件问题 / 4 依赖缺失
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


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=30)
    except Exception as e:  # noqa: BLE001
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


# ------------------------------------------------------------------ 依赖探测

def find_videocaptioner(explicit=None):
    """按 显式指定 → PATH → 当前解释器的 -m → 常见 venv 的顺序找可执行入口。"""
    candidates = []
    if explicit:
        candidates.append([explicit])
    env_cmd = os.environ.get("VC_CMD")
    if env_cmd:
        candidates.append(env_cmd.split())
    hit = shutil.which("videocaptioner")
    if hit:
        candidates.append([hit])
    candidates.append([sys.executable, "-m", "videocaptioner"])
    for base in (
        Path.home() / "vc-venv312" / "Scripts" / "videocaptioner.exe",
        Path.home() / "vc-venv312" / "Scripts" / "videocaptioner",
    ):
        if base.exists():
            candidates.append([str(base)])

    for cmd in candidates:
        p = run(cmd + ["--version"])
        if p.returncode == 0:
            ver = (p.stdout or p.stderr).strip().splitlines()
            return cmd, (ver[0] if ver else "unknown")
    return None, None


def find_bin(name, env_key):
    p = os.environ.get(env_key)
    if p and Path(p).exists():
        return p
    return shutil.which(name)


# ------------------------------------------------------------------ 体检

def probe(ffprobe, ffmpeg, path):
    """优先用 ffprobe；只有 ffmpeg 时退化为解析 `ffmpeg -i` 的 stderr。"""
    if ffprobe:
        p = run([ffprobe, "-v", "error", "-print_format", "json",
                 "-show_format", "-show_streams", str(path)])
        if p.returncode == 0:
            try:
                return json.loads(p.stdout)
            except json.JSONDecodeError:
                pass
    if not ffmpeg:
        return None
    p = run([ffmpeg, "-hide_banner", "-i", str(path)])
    log = p.stderr or p.stdout or ""
    import re as _re
    m = _re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", log)
    dur = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))) if m else 0.0
    vm = _re.search(r"Stream #\S+.*Video:.*?(\d{2,5})x(\d{2,5})", log)
    return {
        "format": {"duration": str(dur)},
        "streams": (
            ([{"codec_type": "video", "width": int(vm.group(1)), "height": int(vm.group(2))}] if vm else [])
            + ([{"codec_type": "audio"}] if _re.search(r"Stream #\S+.*Audio:", log) else [])
        ),
    }


def main():
    ap = argparse.ArgumentParser(description="双语字幕任务前置体检")
    ap.add_argument("input", help="待处理的视频或音频文件")
    ap.add_argument("--target", default="zh-Hans", help="目标语言 BCP47，默认 zh-Hans")
    ap.add_argument("--source-lang", default="auto",
                    help="源音频语言（en/zh/ja…），用于判断 ASR 引擎是否够用；默认 auto 不检查")
    ap.add_argument("--mode", choices=["soft", "hard"], default="hard",
                    help="交付形态：hard=烧进画面，soft=可开关字幕轨")
    ap.add_argument("--asr", default="bijian", help="ASR 引擎，默认 bijian（免费，中英文）")
    ap.add_argument("--style", default="default", help="样式预设名，默认 default")
    ap.add_argument("--vc-cmd", help="显式指定 videocaptioner 命令")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    report = {"ok": True, "blockers": [], "warnings": [], "info": {}}

    src = Path(args.input)
    if not src.exists():
        report["ok"] = False
        report["blockers"].append(f"输入文件不存在：{src}")
        print(f"[x] 输入文件不存在：{src}")
        return 3

    size_mb = round(src.stat().st_size / 1048576, 2)
    report["info"]["file"] = {"path": str(src.resolve()), "size_mb": size_mb}

    # 依赖
    vc_cmd, vc_ver = find_videocaptioner(args.vc_cmd)
    ffmpeg = find_bin("ffmpeg", "FFMPEG_BIN")
    ffprobe = find_bin("ffprobe", "FFPROBE_BIN")
    report["info"]["deps"] = {
        "videocaptioner": vc_ver or None,
        "ffmpeg": ffmpeg or None,
        "ffprobe": ffprobe or None,
    }
    if not vc_cmd:
        report["ok"] = False
        report["blockers"].append(
            "找不到 videocaptioner。装法：用 Python 3.10–3.12 建 venv 后 pip install videocaptioner，"
            "或用 --vc-cmd / 环境变量 VC_CMD 指定入口")
    if not ffmpeg:
        report["ok"] = False
        report["blockers"].append("找不到 ffmpeg（抽音轨/合成必需）")
    if not ffprobe:
        report["warnings"].append("找不到 ffprobe，改用 ffmpeg 解析媒体信息（时长校验精度略低）")

    # 媒体信息
    if ffprobe or ffmpeg:
        info = probe(ffprobe, ffmpeg, src)
        if not info:
            report["warnings"].append("ffprobe 读不出元数据，文件可能损坏或不是媒体文件")
        else:
            streams = info.get("streams", [])
            videos = [s for s in streams if s.get("codec_type") == "video"]
            audios = [s for s in streams if s.get("codec_type") == "audio"]
            dur = float(info.get("format", {}).get("duration") or 0)
            report["info"]["media"] = {
                "duration_sec": round(dur, 2),
                "has_video": bool(videos),
                "has_audio": bool(audios),
                "resolution": (f"{videos[0].get('width')}x{videos[0].get('height')}"
                               if videos else None),
            }
            if not audios:
                report["ok"] = False
                report["blockers"].append("没有音轨，无法做语音识别转写")
            if not videos and args.mode == "hard":
                report["warnings"].append("没有视频轨，只能产出字幕文件，无法烧录")

    # 语言可行性（翻译由模型做，这里只判断 ASR 能不能认出源语言）
    src_lang = (args.source_lang or "auto").lower()
    if (args.asr in ("bijian", "jianying") and src_lang != "auto"
            and not src_lang.startswith("zh") and not src_lang.startswith("en")):
        report["warnings"].append(
            f"ASR 引擎 {args.asr} 只认中文和英语音频；若源音频不是中/英文，改用 --asr whisper-api")

    # 样式预设（pip 包不自带，缺了会让 synthesize 直接失败）
    style_dir = (Path(os.environ.get("LOCALAPPDATA") or str(Path.home()))
                 / "VideoCaptioner" / "VideoCaptioner" / "resource" / "subtitle_style")
    has_styles = style_dir.exists() and any(style_dir.glob("*.json"))
    report["info"]["styles"] = {"dir": str(style_dir), "installed": has_styles}
    if not has_styles:
        report["warnings"].append(
            "字幕样式预设缺失，硬字幕合成会报 Style preset not found；"
            "先跑 python scripts/install_styles.py")

    # 推荐流程：翻译由模型完成，所以是「转写 → 拆条目 → 模型译 → 合并 → 烧录 → 验收」
    steps = [
        f'videocaptioner transcribe "{src.name}" --asr {args.asr} -o subtitles/src.srt',
        "python scripts/segments.py extract subtitles/src.srt -o work/seg.json",
        '（模型写 work/dst.json，格式 {"1": "译文"} 或 {"1": {"dst": "译文", "src": "纠正的原文"}}）',
        "python scripts/segments.py merge work/seg.json --dst work/dst.json "
        "-o subtitles/bilingual.srt",
        f'videocaptioner synthesize "{src.name}" -s subtitles/bilingual.srt '
        f"--subtitle-mode {args.mode} --quality high --style {args.style} "
        f"--layout source-above -o output.mp4",
        f'python scripts/verify.py --subtitle subtitles/bilingual.srt '
        f'--video output.mp4 --source "{src.name}" --bilingual',
    ]
    report["info"]["recommended_steps"] = steps

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("[+] 文件：" + f"{src.name}  {size_mb} MB")
        m = report["info"].get("media")
        if m:
            print(f"    时长 {m['duration_sec']}s · 分辨率 {m['resolution']} · "
                  f"音轨 {'有' if m['has_audio'] else '无'}")
        print(f"[+] videocaptioner: {vc_ver or '缺失'}")
        print(f"[+] ffmpeg: {ffmpeg or '缺失'}")
        print(f"[+] 样式预设: {'已装' if has_styles else '缺失 → python scripts/install_styles.py'}")
        for b in report["blockers"]:
            print(f"[x] {b}")
        for w in report["warnings"]:
            print(f"[!] {w}")
        if report["ok"]:
            print("[+] 体检通过，按顺序执行：")
            for n, s in enumerate(steps, 1):
                print(f"    {n}. {s}")

    if report["blockers"]:
        return 4 if any("videocaptioner" in b or "ffmpeg" in b for b in report["blockers"]) else 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
