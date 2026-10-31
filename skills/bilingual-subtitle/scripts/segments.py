#!/usr/bin/env python3
"""翻译交接脚本：把字幕拆成「待翻译条目」，翻完再合回双语 srt。

为什么需要它：模型直接改 srt 时，长视频几百条时间码极易抄错，
而时间码一旦错位，画面上的字幕就会整体漂移。拆成 JSON 后模型只碰文字，
时间码全程由脚本搬运，错误面从「几百行 srt」缩到「几十行译文」。

用法：
  # 1. 拆出待译条目（只给模型看原文，时间码由脚本保管）
  python scripts/segments.py extract subtitles/en.srt -o work/seg.json

  # 2. 模型写译文到 work/dst.json，格式 {"1": "译文", "2": "译文"} 或 [{"i":1,"dst":"译文"}]
  #    可选写 "src" 同条时一并纠错（ASR 识别错误）

  # 3. 合回双语 srt（默认译文在上，与 synthesize --layout target-above 对应）
  python scripts/segments.py merge work/seg.json --dst work/dst.json -o subtitles/bilingual.srt
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TS = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
CJK = re.compile(r"[\u4e00-\u9fff]")
LATIN = re.compile(r"[A-Za-z]")


# ---------- srt 读写 ----------

def parse_srt(text: str) -> list[dict]:
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    out: list[dict] = []
    for block in re.split(r"\n{2,}", text.strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        idx = 0
        if lines[0].strip().isdigit():
            idx = int(lines[0].strip())
            lines = lines[1:]
        if not lines:
            continue
        m = TS.findall(lines[0])
        if len(m) < 2:
            continue  # 不是时间轴行，跳过（容错）
        body = [l.strip() for l in lines[1:] if l.strip()]
        out.append({
            "i": idx or len(out) + 1,
            "start": lines[0].split("-->")[0].strip(),
            "end": lines[0].split("-->")[1].strip().split(" ")[0],
            "lines": body,
        })
    return out


def fmt_srt(segs: list[dict]) -> str:
    chunks = []
    for n, s in enumerate(segs, 1):
        chunks.append(f"{n}\n{s['start']} --> {s['end']}\n" + "\n".join(s["lines"]))
    return "\n\n".join(chunks) + "\n"


# ---------- 时间码换算 ----------

def ts_to_sec(ts: str) -> float:
    m = TS.match(ts.strip())
    if not m:
        raise ValueError(f"时间码格式不认识：{ts!r}")
    h, mi, s, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def sec_to_ts(sec: float) -> str:
    total = int(round(max(0.0, sec) * 1000))
    h, total = divmod(total, 3_600_000)
    mi, total = divmod(total, 60_000)
    s, ms = divmod(total, 1000)
    return f"{h:02d}:{mi:02d}:{s:02d},{ms:03d}"


def split_time(start: str, end: str, weights: list[int]) -> list[str]:
    """把一条的时间窗按权重（各句原文长度）切开，返回 N+1 个边界时间点。

    按原文长度分配而不是平均分配：原文长短与念出来耗时基本成正比，
    平均分会把短句拖得过长、长句挤得过短。最后一条强制收在原 end 上，
    避免逐段累加的浮点误差让结尾整体后移。
    """
    t0, t1 = ts_to_sec(start), ts_to_sec(end)
    total_w = sum(weights) or len(weights)
    bounds = [start]
    acc = 0
    for w in weights[:-1]:
        acc += w
        bounds.append(sec_to_ts(t0 + (t1 - t0) * acc / total_w))
    bounds.append(end)
    return bounds


# ---------- 语种判定 ----------

def lang_of(text: str) -> str:
    has_cjk = bool(CJK.search(text))
    has_latin = bool(LATIN.search(text))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "cjk"
    if has_latin:
        return "latin"
    return "other"


# ---------- 子命令 ----------

def cmd_extract(args) -> int:
    p = Path(args.subtitle)
    if not p.exists():
        print(f"[x] 找不到字幕：{p}", file=sys.stderr)
        return 3
    segs = parse_srt(p.read_text(encoding="utf-8-sig"))
    if not segs:
        print("[x] 解析出 0 条，检查文件是否为标准 srt", file=sys.stderr)
        return 3

    items = []
    for s in segs:
        # 已有双语的文件：取第一条与语种多数派一致的行作为原文
        src_lines = s["lines"]
        if len(src_lines) >= 2 and lang_of(src_lines[0]) != lang_of(src_lines[1]):
            src = max(src_lines, key=lambda l: len(l))
        else:
            src = " ".join(src_lines)
        items.append({"i": s["i"], "start": s["start"], "end": s["end"], "src": src})

    payload = {
        "_note": ("把译文填进 dst.json：{\"i\": \"译文\"}。"
                  "纠正识别错误用 {\"i\": {\"src\": \"改后的原文\", \"dst\": \"译文\"}}。"
                  "一句拆成多句用 {\"i\": {\"src\": [\"句1\", \"句2\"], \"dst\": [\"译1\", \"译2\"]}}，"
                  "时间码会按各句长度自动分配。"
                  "碎片条目（单独一个 and / you know）写 \"__MERGE_PREV__\" 并入上一条。"),
        "count": len(items),
        "segments": items,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[+] 拆出 {len(items)} 条 → {out}")
    print(f"    下一步：写 {args.out.replace('seg.json', 'dst.json')}，格式 {{\"1\": \"译文\", \"2\": \"译文\"}}")
    return 0


def load_dst(path: Path) -> dict:
    """读取译文。值可以是字符串、数组，或 {"dst": ..., "src": ...}。

    - 字符串：一条字幕译成一条
    - 数组：**一句原文断成多句**时用（ASR 常把两句挤在一条里），
      数组长度即拆分后的条数，src 与 dst 必须等长
    - 带 src 的形式用于顺手纠正 ASR 识别错误——只填 dst 时原文保持转写原样，
      所以听到明显的错词（人名、术语）要在这一步一起改
    """
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, dict):
        if "segments" in data and isinstance(data["segments"], (dict, list)):
            data = data["segments"]
        else:
            data = {k: v for k, v in data.items() if str(k).isdigit()}
        out = {}
        for k, v in data.items():
            if isinstance(v, str):
                out[int(k)] = {"dst": v}
            elif isinstance(v, list):
                out[int(k)] = {"dst": v}
            elif isinstance(v, dict):
                out[int(k)] = {"dst": v.get("dst") or v.get("zh") or "",
                               "src": v.get("src")}
        return out
    if isinstance(data, list):
        out = {}
        for row in data:
            if isinstance(row, dict):
                key = row.get("i") or row.get("id") or row.get("index")
                if key is not None:
                    out[int(key)] = {"dst": row.get("dst") or row.get("zh") or row.get("translation") or "",
                                     "src": row.get("src")}
        return out
    raise ValueError("dst.json 格式不认识：应为 {i: 译文} 字典或 [{i, dst}] 列表")


def _as_parts(val, fallback: str = "") -> list[str]:
    if isinstance(val, list):
        return [str(x).strip() for x in val]
    if val is None or str(val).strip() == "":
        return [fallback]
    return [str(val).strip()]


def norm_en(text: str) -> str:
    """把 ASR 出来的英文整形：ASR 普遍输出全小写、无句末标点、标点前带空格。

    只做大小写与空白层面的事，不改词、不加内容——所以对已经人工校对的文本
    重复跑也安全。专有名词靠 dst.json 里的 src 覆盖，这里不猜。
    """
    s = re.sub(r"\s+", " ", text).strip()
    if not s:
        return s
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)          # 标点前的空格
    s = re.sub(r"([,.;:!?])(?=[A-Za-z])", r"\1 ", s)  # 标点后缺空格
    s = re.sub(r"\bi\b", "I", s)
    s = re.sub(r"\bi'(m|ll|ve|d)\b", lambda m: "I'" + m.group(1), s)
    s = re.sub(r"\bi\s+(am|have|will|would|had)\b", lambda m: "I " + m.group(1), s)
    # 句首大写：按句末标点切成小段，逐段首字母大写
    parts = re.split(r"(?<=[.!?])\s+", s)
    parts = [p[:1].upper() + p[1:] if p else p for p in parts]
    s = " ".join(parts)
    if s[-1] not in ".!?":
        s += "."
    return s


def build_lines(tgt: str, src: str, layout: str, target_first: bool) -> list[str]:
    if layout == "target-only":
        return [tgt]
    if layout == "source-only":
        return [src]
    return [tgt, src] if target_first else [src, tgt]


def cmd_merge(args) -> int:
    seg_path = Path(args.segments)
    if not seg_path.exists():
        print(f"[x] 找不到文件：{seg_path}", file=sys.stderr)
        return 3

    segs = json.loads(seg_path.read_text(encoding="utf-8-sig"))["segments"]

    # 两种交接方式都支持：独立 dst.json（推荐，模型只产出对照表），
    # 或直接在被拆出的 seg.json 里补 dst 字段（少一个文件，适合人工微调）。
    if args.dst:
        dst_path = Path(args.dst)
        if not dst_path.exists():
            print(f"[x] 找不到文件：{dst_path}", file=sys.stderr)
            return 3
        try:
            dst = load_dst(dst_path)
        except Exception as e:  # noqa: BLE001
            print(f"[x] {e}", file=sys.stderr)
            return 3
    else:
        dst = {}
        for s in segs:
            if str(s.get("dst", "")).strip():
                dst[int(s["i"])] = {"dst": s["dst"], "src": s.get("src_override") or s.get("src_fixed")}

    if not dst:
        print("[x] 没有任何译文：传 --dst，或先在 seg.json 每条里补 dst 字段", file=sys.stderr)
        return 2

    # 完整性：每条都要有译文，缺一条就停，不做「跳过继续」的静默降级
    def _blank(v) -> bool:
        if isinstance(v, list):
            return (not v) or any(str(x).strip() == "" for x in v)
        return str(v or "").strip() == ""

    missing = [s["i"] for s in segs if _blank(dst.get(int(s["i"]), {}).get("dst", ""))]
    if missing:
        print(f"[x] 有 {len(missing)} 条缺译文：{missing[:12]}{' ...' if len(missing) > 12 else ''}",
              file=sys.stderr)
        print("    补齐后重跑；不允许留空，空条会在成片上形成空白字幕", file=sys.stderr)
        return 2

    target_first = args.layout in ("target-above", "target-only")
    rows, warns, fixed, split, merged = [], [], 0, 0, 0
    for s in segs:
        i = int(s["i"])
        row = dst[i]

        # 碎片条目（单独一个 "and" / "you know"）不该单独成条：
        # 把时间并入上一条，画面就不会闪一下只有半个词的字幕。
        if isinstance(row["dst"], str) and row["dst"].strip() in ("__MERGE_PREV__", "__MERGE__"):
            if not rows:
                print(f"[x] #{i} 标了并入上一条，但它是第一条", file=sys.stderr)
                return 2
            rows[-1]["end"] = s["end"]
            merged += 1
            continue

        src_parts = _as_parts(row.get("src"), s.get("src", ""))
        tgt_parts = _as_parts(row["dst"])

        if len(tgt_parts) != len(src_parts):
            print(f"[x] #{i} 有 {len(tgt_parts)} 句译文但 {len(src_parts)} 句原文，"
                  f"断句必须成对给出", file=sys.stderr)
            print(f"    原文：{src_parts}\n    译文：{tgt_parts}", file=sys.stderr)
            return 2

        if row.get("src") is not None:
            flat_old = " ".join(str(x) for x in _as_parts(s.get("src", "")))
            flat_new = " ".join(src_parts)
            if flat_new != flat_old:
                fixed += 1

        if args.normalize_en:
            src_parts = [x if CJK.search(x) else norm_en(x) for x in src_parts]

        n = len(tgt_parts)
        if n == 1:
            lines = build_lines(tgt_parts[0], src_parts[0], args.layout, target_first)
            rows.append({"start": s["start"], "end": s["end"], "lines": lines})
            if CJK.search(tgt_parts[0]) and not _wrap_ok(tgt_parts[0], args.max_cjk):
                warns.append(f"#{i} 中文 {len(tgt_parts[0])} 字，超过 {args.max_cjk} 字建议值")
            continue

        # 一条拆成多条：时间窗按各句原文长度分配
        bounds = split_time(s["start"], s["end"], [max(1, len(p)) for p in src_parts])
        dur = ts_to_sec(s["end"]) - ts_to_sec(s["start"])
        for k in range(n):
            st, en = bounds[k], bounds[k + 1]
            piece = ts_to_sec(en) - ts_to_sec(st)
            if piece < 0.4:
                warns.append(f"#{i} 第 {k + 1} 句只有 {piece:.2f}s，可能一闪而过")
            lines = build_lines(tgt_parts[k], src_parts[k], args.layout, target_first)
            rows.append({"start": st, "end": en, "lines": lines})
            if CJK.search(tgt_parts[k]) and not _wrap_ok(tgt_parts[k], args.max_cjk):
                warns.append(f"#{i}.{k + 1} 中文 {len(tgt_parts[k])} 字，超过 {args.max_cjk} 字建议值")
        split += 1
        if dur / n < 0.8:
            warns.append(f"#{i} 拆成 {n} 句后平均仅 {dur / n:.2f}s/句，建议合并或延长")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\ufeff" + fmt_srt(rows), encoding="utf-8", newline="\n")

    print(f"[+] 合并 {len(rows)} 条 → {out}")
    if split:
        print(f"    其中 {split} 条被断句拆分（原 {len(segs)} 条 → {len(rows)} 条）")
    if merged:
        print(f"    其中 {merged} 条碎片并入上一条")
    print(f"    版式：{'译文在上' if target_first else '原文在上'}"
          f"{'（仅保留一种语言）' if args.layout.endswith('only') else ''}")
    if fixed:
        print(f"    已应用 {fixed} 条原文纠正")
    if warns:
        print(f"[!] 告警 {len(warns)} 条（不影响交付，建议处理）：")
        for w in warns[:10]:
            print("    " + w)
    return 0


def _wrap_ok(text: str, limit: int = 18) -> bool:
    # 按标点切句后判断最长一段
    parts = [p for p in re.split(r"[，。！？；：、,.!?;:]", text) if p]
    return all(len(p) <= limit for p in parts) if parts else len(text) <= limit


def cmd_concat(args) -> int:
    """拼接多个 srt 片断，重新编号、只保留一个 BOM。

    直接用 `cat part_*.srt > out.srt` 会踩两个坑：每个分片的编号都从 1 开始，
    且第 2 个分片的 BOM 会跑到文件中间，部分播放器会把它渲染成乱码方块。
    """
    rows = []
    for p in args.inputs:
        path = Path(p)
        if not path.exists():
            print(f"[x] 找不到分片：{path}", file=sys.stderr)
            return 3
        rows.extend(parse_srt(path.read_text(encoding="utf-8-sig")))

    if not rows:
        print("[x] 没有解析到任何条目", file=sys.stderr)
        return 3

    # 顺带校验时间轴单调，拼接顺序错（比如 part_10 排在 part_2 前面）能立刻发现
    bad = [i for i in range(1, len(rows)) if rows[i]["start"] < rows[i - 1]["start"]]
    if bad:
        print(f"[!] 时间轴在第 {bad[0]} 条处倒退，分片顺序可能不对：{[str(x) for x in args.inputs]}",
              file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\ufeff" + fmt_srt(rows), encoding="utf-8", newline="\n")
    print(f"[+] 拼接 {len(args.inputs)} 个分片 / {len(rows)} 条 → {out}")
    return 0


def cmd_audit(args) -> int:
    """扫一遍转写结果，指出哪些条目需要断句/合并，而不是让人肉眼过几百条。

    判据直接对应 SKILL.md 的三条：停留 1–4 秒、中文 ≤ 18 字、英文 ≤ 12 词。
    这里只在明显越界时报警，避免把「3 秒 12 词」这种正常条目也淹没进来。
    """
    p = Path(args.source)
    if not p.exists():
        print(f"[x] 找不到文件：{p}", file=sys.stderr)
        return 3

    if p.suffix.lower() == ".json":
        data = json.loads(p.read_text(encoding="utf-8-sig"))
        segs = data.get("segments", data)
        rows = [(int(s["i"]), s["start"], s["end"], str(s.get("src", ""))) for s in segs]
    else:
        parsed = parse_srt(p.read_text(encoding="utf-8-sig"))
        rows = [(int(s["i"]), s["start"], s["end"], " ".join(s["lines"])) for s in parsed]

    if not rows:
        print("[x] 没有解析到任何条目", file=sys.stderr)
        return 3

    frag, long_, ok = [], [], 0
    for i, st, en, text in rows:
        dur = ts_to_sec(en) - ts_to_sec(st)
        cjk = len(CJK.findall(text))
        words = len(re.findall(r"[A-Za-z][A-Za-z']*", text))
        unit = cjk if cjk else words
        # 碎片只看「太短」和「只有一个词且极短」两种。
        # 不能按「词数 ≤ 2」判：They're amazing / 太好了 都是完整短句，2 个词很正常。
        if dur < args.min_sec or (unit <= 1 and dur < 1.5):
            frag.append((i, st, en, dur, unit, text))
        elif dur > args.max_sec or cjk > args.max_cjk or (not cjk and words > args.max_words):
            n = max(2, -(-int(dur) // 3))  # 每段约 3 秒，向上取整
            long_.append((i, st, en, dur, unit, text, n))
        else:
            ok += 1

    print(f"[*] 检查 {len(rows)} 条：{ok} 条正常，{len(frag)} 条疑似碎片，{len(long_)} 条过长")
    if frag:
        print("\n[!] 疑似碎片（建议在 dst.json 里写 \"__MERGE_PREV__\" 并入上一条）：")
        for i, st, en, dur, unit, text in frag[:15]:
            print(f"    #{i:<3} {dur:4.2f}s  {unit:>2} 词/字  {text[:46]!r}")
        if len(frag) > 15:
            print(f"    …… 另有 {len(frag) - 15} 条")
    if long_:
        print("\n[!] 过长（建议拆成数组，或缩短译文）：")
        for i, st, en, dur, unit, text, n in long_[:15]:
            print(f"    #{i:<3} {dur:4.2f}s  {unit:>2} 词/字  建议拆 {n} 段  {text[:40]!r}")
        if len(long_) > 15:
            print(f"    …… 另有 {len(long_) - 15} 条")

    if args.json:
        print(json.dumps({
            "total": len(rows), "ok": ok,
            "fragments": [{"i": r[0], "dur": round(r[3], 2), "text": r[5]} for r in frag],
            "too_long": [{"i": r[0], "dur": round(r[3], 2), "suggest_split": r[6], "text": r[5]} for r in long_],
        }, ensure_ascii=False, indent=2))
    return 0 if not (frag or long_) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="字幕翻译交接：拆条目 / 合回双语 srt")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="扫出需要断句或合并的条目")
    a.add_argument("source", help="seg.json 或 srt")
    a.add_argument("--min-sec", type=float, default=0.8, help="短于此时长视为碎片")
    a.add_argument("--max-sec", type=float, default=5.0, help="长于此时长视为过长")
    a.add_argument("--max-cjk", type=int, default=18, help="中文单条上限")
    a.add_argument("--max-words", type=int, default=14, help="英文单词上限")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_audit)

    e = sub.add_parser("extract", help="把 srt 拆成待译 JSON")
    e.add_argument("subtitle")
    e.add_argument("-o", "--out", default="work/seg.json")
    e.set_defaults(func=cmd_extract)

    m = sub.add_parser("merge", help="把译文合回双语 srt")
    m.add_argument("segments")
    m.add_argument("--dst", help="译文 JSON；省略时读 seg.json 里各自的 dst 字段")
    m.add_argument("-o", "--out", default="subtitles/bilingual.srt")
    m.add_argument("--layout", default="target-above",
                   choices=["target-above", "source-above", "target-only", "source-only"],
                   help="target-above=译文在上（默认，配合 synthesize 时不要再加 --layout）")
    m.add_argument("--max-cjk", type=int, default=18, help="中文单行建议上限")
    m.add_argument("--normalize-en", action="store_true",
                   help="把英文原文整形（首字母大写、i→I、补句末标点、清理标点空格）")
    m.set_defaults(func=cmd_merge)

    c = sub.add_parser("concat", help="拼接多个 srt 分片（重新编号、去重复 BOM）")
    c.add_argument("inputs", nargs="+")
    c.add_argument("-o", "--out", default="subtitles/bilingual.srt")
    c.set_defaults(func=cmd_concat)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
