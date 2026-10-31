#!/usr/bin/env python3
"""技能检查与打包：把「审核驳回」挡在上传之前。

用法:
    python build/pack.py check skills/bilingual-subtitle
    python build/pack.py pack  skills/bilingual-subtitle
    python build/pack.py pack  skills/bilingual-subtitle --allow-placeholder

检查项对应技能市场的实际驳回原因:
    1. frontmatter 8 个必填字段齐全且非空
    2. name 字段与目录名一致（否则 zip 内根目录会对不上）
    3. zip 内只允许 SKILL.md、references/、scripts/、templates/ 四类内容
       （CHANGELOG.md 留在仓库就近维护，打包时剔除）
    4. 无 __pycache__、无空目录
    5. author 不是占位符（打包时判为错误，可用 --allow-placeholder 跳过）

退出码: 0 通过 / 3 校验失败 / 4 路径有问题
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

REQUIRED_FIELDS = [
    "name",
    "display_name",
    "display_name_en",
    "description",
    "description_zh",
    "description_en",
    "version",
    "author",
]

# 技能市场允许进入 zip 的顶层内容，白名单之外的目录一律不收
ALLOWED_TOP_FILES = {"SKILL.md"}
ALLOWED_TOP_DIRS = {"references", "scripts", "templates"}

# 留在仓库里、但不上传的文件。白名单约束的是 zip 内容，不是目录里能放什么，
# 所以变更记录可以放在技能目录里就近维护，打包时剔除。
REPO_ONLY_TOP_FILES = {"CHANGELOG.md"}

PLACEHOLDER_AUTHORS = {
    "",
    "个人开发者",
    "开发者",
    "author",
    "your-name",
    "your_name",
    "todo",
    "tbd",
}

VERSION_RE = re.compile(r"^\d+\.\d+\.\d+")


def parse_frontmatter(path: Path):
    """解析 SKILL.md 头部的 --- 块，返回 (dict, 全文)。不做完整 YAML。"""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text

    meta = {}
    for line in lines[1:end]:
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        else:
            val = val.strip("'\"")
        meta[key] = val.strip()
    return meta, text


def scan_structure(skill_dir: Path):
    """返回 (文件列表, 问题列表)。文件列表是相对路径。"""
    files, problems = [], []

    for p in sorted(skill_dir.rglob("*")):
        rel = p.relative_to(skill_dir)
        parts = rel.parts

        shown = rel.as_posix()

        if p.is_dir():
            if p.name == "__pycache__":
                problems.append(f"含 __pycache__ 目录: {shown}")
            elif not any(p.iterdir()):
                problems.append(f"空目录: {shown}")
            continue

        if "__pycache__" in parts or p.suffix in {".pyc", ".pyo"}:
            problems.append(f"含 Python 字节码: {shown}")
            continue

        if len(parts) == 1:
            if p.name in REPO_ONLY_TOP_FILES:
                # 只留仓库，不进 zip
                continue
            if p.name not in ALLOWED_TOP_FILES:
                problems.append(f"顶层文件不在白名单: {shown}")
        elif parts[0] not in ALLOWED_TOP_DIRS:
            problems.append(f"顶层目录不在白名单: {shown}")

        files.append(rel)

    return files, problems


def check_latest_changelog(skill_dir: Path, version: str):
    """CHANGELOG 最新条目的版本应与 SKILL.md 的 version 一致。只告警。"""
    changelog = skill_dir / "CHANGELOG.md"
    if not changelog.is_file():
        return "缺少 CHANGELOG.md，建议补上（发布时要用更新说明）"
    text = changelog.read_text(encoding="utf-8")
    m = re.search(r"^##\s*\[?v?(\d+\.\d+\.\d+)", text, re.MULTILINE)
    if not m:
        return "CHANGELOG.md 里找不到形如 '## [1.0.0]' 的版本标题"
    if m.group(1) != version:
        return f"CHANGELOG 最新是 {m.group(1)}，SKILL.md 是 {version}，两边对不上"
    return None


def inspect(skill_dir: Path, allow_placeholder: bool = False, for_pack: bool = False):
    """执行全部检查，返回 (meta, files, 错误列表, 告警列表)。"""
    errors, warnings = [], []

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return {}, [], [f"{skill_dir} 下没有 SKILL.md"], []

    meta, _ = parse_frontmatter(skill_md)
    if not meta:
        errors.append("SKILL.md 开头没有 --- 包裹的 frontmatter")

    missing = [f for f in REQUIRED_FIELDS if not meta.get(f)]
    if missing:
        errors.append("缺少必填字段: " + "、".join(missing))

    name = meta.get("name", "")
    if name and name != skill_dir.name:
        errors.append(f"name 字段是 '{name}'，与目录名 '{skill_dir.name}' 不一致")

    version = meta.get("version", "")
    if version and not VERSION_RE.match(version):
        errors.append(f"version '{version}' 不是 x.y.z 形式")

    files, struct_problems = scan_structure(skill_dir)
    errors.extend(struct_problems)

    if not any(f.as_posix() == "SKILL.md" for f in files):
        errors.append("zip 内缺少 SKILL.md")

    author = meta.get("author", "").strip()
    # 作者为空时「缺少必填字段」已经报过，这里只说「填了但填的是占位符」
    if author and (author.lower() in PLACEHOLDER_AUTHORS or author in PLACEHOLDER_AUTHORS):
        msg = f"author 仍是占位符 '{author}'，上架前必须换成入驻主体名"
        (errors if for_pack and not allow_placeholder else warnings).append(msg)

    if version:
        warn = check_latest_changelog(skill_dir, version)
        if warn:
            warnings.append(warn)

    return meta, files, errors, warnings


def cmd_check(args):
    skill_dir = Path(args.skill).resolve()
    if not skill_dir.is_dir():
        print(f"路径不存在: {skill_dir}", file=sys.stderr)
        return 4

    meta, files, errors, warnings = inspect(skill_dir)
    for w in warnings:
        print(f"  提醒  {w}")
    for e in errors:
        print(f"  错误  {e}")

    if errors:
        print(f"\n{len(errors)} 项不通过，先修再打包")
        return 3

    print(f"\n通过：{meta.get('name')} v{meta.get('version')}，{len(files)} 个文件")
    return 0


def cmd_pack(args):
    skill_dir = Path(args.skill).resolve()
    if not skill_dir.is_dir():
        print(f"路径不存在: {skill_dir}", file=sys.stderr)
        return 4

    meta, files, errors, warnings = inspect(
        skill_dir, allow_placeholder=args.allow_placeholder, for_pack=True
    )
    for w in warnings:
        print(f"  提醒  {w}")
    for e in errors:
        print(f"  错误  {e}")
    if errors:
        print(f"\n{len(errors)} 项不通过，已中止打包")
        return 3

    name, version = meta["name"], meta["version"]
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}-{version}.zip"

    # zip 内以技能名做根目录，与市场上传要求一致
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(skill_dir / rel, f"{name}/{rel.as_posix()}")

    size = out.stat().st_size / 1024
    print(f"\n已打包 {out}")
    print(f"  {len(files)} 个文件，{size:.1f} KB，zip 内根目录 {name}/")
    return 0


def main():
    ap = argparse.ArgumentParser(description="技能检查与打包")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="只做合规检查")
    c.add_argument("skill")
    c.set_defaults(func=cmd_check)

    p = sub.add_parser("pack", help="检查通过后打包 zip")
    p.add_argument("skill")
    p.add_argument("-o", "--out", default="build/out", help="输出目录，默认 build/out")
    p.add_argument(
        "--allow-placeholder",
        action="store_true",
        help="允许 author 为占位符（仅本地试打包用）",
    )
    p.set_defaults(func=cmd_pack)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
