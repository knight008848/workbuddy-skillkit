#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify.py — 字幕/成片验收

把「看着还行」变成可判定的清单：编码、双语结构、每行长度、时间轴、时长一致性。
任何一项不过就以非零码退出，便于在流程里卡住返工。

用法：
    python scripts/verify.py --subtitle out.srt
    python scripts/verify.py --subtitle out.srt --video out.mp4 --source in.mp4 --bilingual
    python scripts/verify.py --subtitle out.srt --json

退出码：0 全部通过 / 1 有失败项
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TS = r"(\d{1,3}):(\d{2}):(\d{2})[,.](\d{1,3})"
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN = re.compile(r"[A-Za-z]")


def ok(msg):
    print(f"  [✓] {msg}")


def bad(msg):
    print(f"  [x] {msg}")


def warn(msg):
    print(f"  [!] {msg}")


# ------------------------------------------------------------------ 解析

def parse_ts(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / (10 ** len(ms))


def parse_sub(path: Path):
    raw = path.read_bytes()
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace")
    blocks = []
    for chunk in re.split(r"\n\s*\n", text.strip()):
        lines = [l.rstrip() for l in chunk.split("\n") if l.strip()]
        if not lines:
            continue
        ts_idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if ts_idx is None:
            continue
        m = re.search(TS + r"\s*-->\s*" + TS, lines[ts_idx])
        if not m:
            continue
        g = m.groups()
        body = [l.strip() for l in lines[ts_idx + 1:]]
        blocks.append({
            "start": parse_ts(*g[:4]),
            "end": parse_ts(*g[4:]),
            "lines": body,
            "text": " ".join(body),
        })
    return blocks, has_bom


def probe_duration(ffprobe, path: Path, ffmpeg=None):
    """优先 ffprobe；退化到解析 `ffmpeg -i` 的 Duration 行。"""
    if ffprobe:
        try:
            p = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, timeout=30)
            return float(p.stdout.strip())
        except Exception:  # noqa: BLE001
            pass
    if ffmpeg:
        try:
            p = subprocess.run([ffmpeg, "-hide_banner", "-i", str(path)],
                               capture_output=True, text=True, timeout=30)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", p.stderr or "")
            if m:
                return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except Exception:  # noqa: BLE001
            pass
    return None


# ------------------------------------------------------------------ 主流程

def main():
    ap = argparse.ArgumentParser(description="字幕/成片验收")
    ap.add_argument("--subtitle", required=True, help="字幕文件（.srt/.ass 的 srt 形态）")
    ap.add_argument("--video", help="成片路径（可选，用于时长校验）")
    ap.add_argument("--source", help="源视频路径（可选，与成片比对时长）")
    ap.add_argument("--bilingual", action="store_true", help="要求双语结构（每条含两种语言）")
    ap.add_argument("--max-cjk", type=int, default=18, help="每行最多中文字数，默认 18")
    ap.add_argument("--max-latin-words", type=int, default=12, help="每行最多英文单词数，默认 12")
    ap.add_argument("--max-overlap", type=float, default=0.0, help="允许的时间重叠秒数，默认 0")
    ap.add_argument("--duration-tolerance", type=float, default=0.5,
                    help="时长允许偏差秒数，默认 0.5")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    sub = Path(args.subtitle)
    result = {"pass": True, "failures": [], "warnings": [], "stats": {}}

    def fail(m):
        result["pass"] = False
        result["failures"].append(m)

    def wrn(m):
        result["warnings"].append(m)

    if not sub.exists():
        fail(f"字幕文件不存在：{sub}")
        print(f"[x] 字幕文件不存在：{sub}")
        return 1

    blocks, has_bom = parse_sub(sub)
    if not blocks:
        fail("解析不出任何字幕条目（空文件或格式错误）")
        print("[x] 解析不出字幕条目")
        return 1

    print(f"[*] 检查 {sub.name}：{len(blocks)} 条")

    # 1. 编码
    if sub.suffix.lower() == ".srt":
        if has_bom:
            ok("编码 UTF-8 with BOM（Windows 播放器友好）")
        else:
            wrn("srt 无 BOM，部分 Windows 播放器可能显示乱码")
    if "\ufffd" in sub.read_bytes().decode("utf-8-sig", errors="replace"):
        fail("文件含替换字符，疑似编码错乱")

    # 2. 双语结构
    bilingual_blocks = 0
    for b in blocks:
        if len(b["lines"]) >= 2:
            joined = " ".join(b["lines"])
            if CJK.search(joined) and LATIN.search(joined):
                bilingual_blocks += 1
    ratio = bilingual_blocks / len(blocks)
    result["stats"]["bilingual_ratio"] = round(ratio, 3)
    if args.bilingual:
        if ratio >= 0.9:
            ok(f"双语结构 {bilingual_blocks}/{len(blocks)} 条（{ratio:.0%}）")
        elif ratio >= 0.6:
            wrn(f"仅 {ratio:.0%} 条目是双语，可能是单语混排或断句不一致")
        else:
            fail(f"双语条目只有 {ratio:.0%}，未达到双语交付标准")

    # 3. 每行长度
    over_cjk, over_latin = [], []
    for i, b in enumerate(blocks, 1):
        for line in b["lines"]:
            cjk_count = len(CJK.findall(line))
            latin_words = len(re.findall(r"[A-Za-z][A-Za-z'’-]*", line))
            if cjk_count > args.max_cjk:
                over_cjk.append((i, cjk_count, line[:24]))
            if latin_words > args.max_latin_words:
                over_latin.append((i, latin_words, line[:24]))
    if over_cjk:
        wrn(f"{len(over_cjk)} 行中文超 {args.max_cjk} 字，例：第 {over_cjk[0][0]} 条 "
            f"{over_cjk[0][1]} 字「{over_cjk[0][2]}…」")
    else:
        ok(f"所有中文行 ≤ {args.max_cjk} 字")
    if over_latin:
        wrn(f"{len(over_latin)} 行英文超 {args.max_latin_words} 词，例：第 {over_latin[0][0]} 条 "
            f"{over_latin[0][1]} 词")
    else:
        ok(f"所有英文行 ≤ {args.max_latin_words} 词")

    # 4. 时间轴
    prev_end = -1.0
    overlaps, zero_len = 0, 0
    for b in blocks:
        if b["end"] <= b["start"]:
            zero_len += 1
        if prev_end > b["start"] + args.max_overlap:
            overlaps += 1
        prev_end = b["end"]
    if zero_len:
        fail(f"{zero_len} 条时长为 0 或负值")
    else:
        ok("时长均为正")
    if overlaps:
        fail(f"{overlaps} 处时间轴重叠（超过 {args.max_overlap}s 容差）")
    else:
        ok("时间轴无重叠")

    dur_span = blocks[-1]["end"] - blocks[0]["start"]
    result["stats"]["first_start"] = round(blocks[0]["start"], 2)
    result["stats"]["last_end"] = round(blocks[-1]["end"], 2)
    result["stats"]["span_sec"] = round(dur_span, 2)
    if blocks[0]["start"] > 10:
        wrn(f"首条字幕在 {blocks[0]['start']:.1f}s 才开始，确认开头是否本来没人说话")

    # 5. 时长一致性
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if (ffprobe or ffmpeg) and args.video:
        vd = probe_duration(ffprobe, Path(args.video), ffmpeg)
        if vd is None:
            wrn("读不出成片时长，跳过一致性校验")
        else:
            result["stats"]["video_duration"] = round(vd, 2)
            if args.source:
                sd = probe_duration(ffprobe, Path(args.source), ffmpeg)
                if sd:
                    diff = abs(vd - sd)
                    result["stats"]["duration_diff"] = round(diff, 2)
                    if diff <= args.duration_tolerance:
                        ok(f"成片时长 {vd:.1f}s 与源片 {sd:.1f}s 一致（差 {diff:.2f}s）")
                    else:
                        fail(f"成片时长 {vd:.1f}s 与源片 {sd:.1f}s 差 {diff:.1f}s，超过容差")
            if blocks[-1]["end"] > vd + 1:
                fail(f"末条字幕结束（{blocks[-1]['end']:.1f}s）晚于成片时长（{vd:.1f}s）")
    elif args.video:
        wrn("没有 ffprobe，跳过时长校验")

    # 汇总
    print()
    for f in result["failures"]:
        bad(f)
    for w in result["warnings"]:
        warn(w)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(("[+] 验收通过" if result["pass"] else "[-] 验收未通过，见上方 [x] 项"))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
