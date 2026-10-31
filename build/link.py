#!/usr/bin/env python3
"""把 skills/<name> 链接进 WorkBuddy 用户技能目录，改一处两份同步。

不链接、只复制的话，改完 A 测试 B，是「改了半天没生效」的头号原因。

用法:
    python build/link.py link bilingual-subtitle
    python build/link.py unlink bilingual-subtitle
    python build/link.py list

Windows 用目录联接（junction，不需要管理员权限），其他系统用软链接。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

SKILLS_HOME = Path.home() / ".workbuddy" / "skills"

# mklink / rmdir 在中文 Windows 上输出 GBK，按 UTF-8 解会抛 UnicodeDecodeError
# （异常发生在 subprocess 的读线程里，主流程看着"成功"，退出时才炸出 traceback）。
_SUBPROC = {"capture_output": True, "text": True, "errors": "replace"}


def is_link(p: Path) -> bool:
    if p.is_symlink():
        return True
    # Windows junction 在 pathlib 里既不是 symlink 也不暴露标志，用 os 层面的判断
    return os.path.isdir(p) and bool(getattr(os.lstat(p), "st_file_attributes", 0) & 0x400)


def make_link(src: Path, dst: Path):
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], **_SUBPROC)
        if r.returncode != 0:
            raise RuntimeError((r.stdout + r.stderr).strip())
    else:
        dst.symlink_to(src, target_is_directory=True)


def cmd_link(args):
    src = (Path("skills") / args.name).resolve()
    if not (src / "SKILL.md").is_file():
        print(f"找不到 skills/{args.name}/SKILL.md", file=sys.stderr)
        return 4

    SKILLS_HOME.mkdir(parents=True, exist_ok=True)
    dst = SKILLS_HOME / args.name

    if dst.exists() or is_link(dst):
        if is_link(dst):
            print(f"已存在链接，先移除再建: {dst}")
            remove_link(dst)
        else:
            print(f"{dst} 是真实目录，未做改动。", file=sys.stderr)
            print(" 如果它是旧的手工副本，先自行备份并删除，再重跑本命令。", file=sys.stderr)
            return 3

    try:
        make_link(src, dst)
    except Exception as exc:  # noqa: BLE001
        print(f"创建链接失败: {exc}", file=sys.stderr)
        return 3

    print(f"已链接 {src}\n    -> {dst}")
    print("重启 WorkBuddy 会话后生效；之后改 skills/ 下的文件即可直接测。")
    return 0


def remove_link(dst: Path):
    if os.name == "nt":
        # 目录联接用 rmdir 摘掉，不会删到源目录内容
        subprocess.run(["cmd", "/c", "rmdir", str(dst)], **_SUBPROC)
    else:
        dst.unlink()


def cmd_unlink(args):
    dst = SKILLS_HOME / args.name
    if not (dst.exists() or is_link(dst)):
        print(f"没有这个链接: {dst}")
        return 0
    if not is_link(dst):
        print(f"{dst} 是真实目录，不删。确需删除请手动处理。", file=sys.stderr)
        return 3
    remove_link(dst)
    print(f"已移除 {dst}")
    return 0


def cmd_list(_args):
    if not SKILLS_HOME.is_dir():
        print(f"{SKILLS_HOME} 不存在")
        return 0
    for p in sorted(SKILLS_HOME.iterdir()):
        tag = "链接" if is_link(p) else "实体"
        print(f"  [{tag}] {p.name}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="WorkBuddy 技能目录链接管理")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, func in (("link", cmd_link), ("unlink", cmd_unlink)):
        p = sub.add_parser(name)
        p.add_argument("name", help="skills/ 下的技能目录名")
        p.set_defaults(func=func)

    lp = sub.add_parser("list", help="看当前安装了哪些")
    lp.set_defaults(func=cmd_list)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
