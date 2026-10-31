#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_styles.py — 补装字幕样式预设

pip 安装的 videocaptioner **不自带样式预设文件**，`--style` 和 `--style-override`
会因为找不到 `default` 预设直接报 `Style preset not found`。
本脚本把技能内置的预设复制到 videocaptioner 读取的目录，幂等，可反复执行。

用法：
    python scripts/install_styles.py                # 安装到默认目录
    python scripts/install_styles.py --dir <目录>    # 指定目录
    python scripts/install_styles.py --check        # 只检查，不写入
"""

import argparse
import json
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = SKILL_ROOT / "templates" / "styles" / "presets"


# 中文字体候选，按优先级排列。不同系统装的位置不一样，逐个试。
CJK_FONT_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/msyh.ttc",          # 微软雅黑
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",        # 黑体
    "C:/Windows/Fonts/simsun.ttc",        # 宋体
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]


def find_cjk_font() -> str | None:
    """返回本机可用的中文字体文件路径。"""
    for p in CJK_FONT_CANDIDATES:
        if Path(p).exists():
            return p
    return None


def adapt(preset: dict, font_path: str | None) -> dict:
    """按渲染模式修正 font_name。

    两种模式的 font_name 语义完全不同，这是 videocaptioner 的一个隐性坑：
      - mode=ass     ：字体名被写进 ASS 的 Style 行，交给 libass/fontconfig 解析，
                       必须写**字体族名**（如 Microsoft YaHei），写路径反而找不到
      - mode=rounded ：走 PIL 的 ImageFont.truetype()，它把字符串当**文件路径**，
                       写族名会 OSError 再一路 fallback，必须写字体文件绝对路径
    """
    if not font_path:
        return preset
    if preset.get("mode") != "rounded":
        return preset  # ass 模式保持族名不动
    preset["font_name"] = font_path
    if isinstance(preset.get("secondary"), dict):
        preset["secondary"]["font_name"] = font_path
    return preset


def default_styles_dir() -> Path:
    """与 videocaptioner 的 _default_styles_dir() 保持一致。"""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "VideoCaptioner" / "VideoCaptioner" / "resource" / "subtitle_style"


def main():
    ap = argparse.ArgumentParser(description="安装字幕样式预设")
    ap.add_argument("--dir", help="目标目录，默认与 videocaptioner 一致")
    ap.add_argument("--check", action="store_true", help="只检查是否齐全")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的同名预设")
    args = ap.parse_args()

    target = Path(args.dir) if args.dir else default_styles_dir()

    if not SRC_DIR.exists():
        print(f"[x] 找不到内置预设目录：{SRC_DIR}")
        return 1

    presets = sorted(SRC_DIR.glob("*.json"))
    if not presets:
        print(f"[x] {SRC_DIR} 里没有预设文件")
        return 1

    if args.check:
        missing = [p.name for p in presets if not (target / p.name).exists()]
        print(f"[*] 目标目录：{target}")
        font = find_cjk_font()
        print(f"[*] 中文字体：{font or '未找到，rounded 模式会回退到默认字体（可能出方块）'}")
        if not target.exists():
            print("[x] 目录不存在，预设未安装")
            return 1
        if missing:
            print(f"[!] 缺少 {len(missing)} 个预设：" + ", ".join(missing))
            return 1
        print(f"[+] {len(presets)} 个预设齐全")
        return 0

    font = find_cjk_font()
    target.mkdir(parents=True, exist_ok=True)
    copied, skipped = 0, 0
    for p in presets:
        dst = target / p.name
        if dst.exists() and not args.force:
            skipped += 1
            continue
        try:
            preset = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"[!] {p.name} 解析失败，跳过：{e}")
            continue
        preset = adapt(preset, font)
        dst.write_text(json.dumps(preset, ensure_ascii=False, indent=2), encoding="utf-8")
        copied += 1
    # 校验 JSON 合法
    bad = []
    for p in target.glob("*.json"):
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            bad.append(p.name)
    print(f"[+] 已安装 {copied} 个，跳过 {skipped} 个 → {target}")
    if font:
        print(f"[+] rounded 类预设已绑定字体文件：{font}")
    else:
        print("[!] 没找到中文字体，rounded 模式可能显示方块；ass 模式不受影响")
    if bad:
        print(f"[!] 以下预设 JSON 解析失败：{', '.join(bad)}")
        return 1
    print("    现在可以给 synthesize 传 --style default|vertical|anime|rounded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
