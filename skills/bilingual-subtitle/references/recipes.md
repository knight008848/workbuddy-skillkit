# 场景配方（bilingual-subtitle）

所有场景的翻译都由模型完成，**不调用 videocaptioner 的在线翻译接口**（理由见 SKILL.md 第九节）。
因此每条配方只写「和通用骨架不一样的部分」，避免五行命令重复十遍。

## 通用骨架

```bash
IN=input.mp4
OUT=output.mp4

# 1 体检
python scripts/preflight.py "$IN"

# 2 转写（只要原文）
videocaptioner transcribe "$IN" --asr bijian -o subtitles/src.srt

# 3 拆条目
python scripts/segments.py extract subtitles/src.srt -o work/seg.json

# 4 模型翻译 → work/dst.json
#   {"1": "译文"}  或  {"1": {"dst": "译文", "src": "纠正后的原文"}}

# 5 合回双语 srt
python scripts/segments.py merge work/seg.json --dst work/dst.json -o subtitles/bilingual.srt

# 6 烧录（注意 source-above，与 merge 的方向相反）
videocaptioner synthesize "$IN" -s subtitles/bilingual.srt \
  --subtitle-mode hard --quality high --style default --layout source-above -o "$OUT"

# 7 验收
python scripts/verify.py --subtitle subtitles/bilingual.srt \
  --video "$OUT" --source "$IN" --bilingual
```

---

## 1. 英文视频 → 中英双语（最常见）

骨架原样即可。翻译时的硬约束：

- 中文每行 ≤ 18 字，超了先删虚词，不要断成两句
- 英文保留原字幕的换行位置，不要重排
- 影视台词优先「像人说话」，书面语和长定语一律拆开

## 2. 中文视频 → 中英双语（面向海外）

只有两处不同：

```bash
# 第 4 步：译文是英文
# {"1": {"dst": "The core idea is simple: predict the next token."}}

# 第 6 步：英文在上更符合外语观众习惯
videocaptioner synthesize "$IN" -s subtitles/bilingual.srt \
  --subtitle-mode hard --quality high --style default --layout target-above -o "$OUT"
```

英文行宽控制在 ≤ 12 词，超出就把中文原文那一步的译文写得更紧。

## 3. 已有字幕文件 → 双语（不重新转写）

跳过第 2 步，`segments.py extract` 直接吃现成 srt：

```bash
python scripts/segments.py extract in.srt -o work/seg.json
```

好处是时间轴**完全不动**，音画绝不会错位。适用于用户已经调好轴、只缺中文的情况。

原字幕若是 ass，先转 srt 再进来：`ffmpeg -i in.ass in.srt`。

## 4. 只要字幕文件，不要成片

跑到第 5 步停。产物 `subtitles/bilingual.srt` 是 UTF-8 with BOM，Windows 播放器和
Premiere / 剪映都能直接读。

需要 ass（带样式、做特效）时多跑一步：

```bash
ffmpeg -i subtitles/bilingual.srt subtitles/bilingual.ass
```

## 5. 术语表（人名、品牌、专有名词）

术语**写在给模型的任务里**，不进命令行——这是模型翻译相对在线接口的主要优势，别浪费。

写法：在翻译时先定一张表，逐条按表走。

```
Lanterns → 灯影
Max → 保留英文 Max
Ep. → 第…集
```

译完抽查：`python scripts/segments.py merge ... ` 后直接 grep 一遍人名：

```bash
grep -c "灯影" subtitles/bilingual.srt   # 应等于原文出现次数
grep -n "Lanterns" subtitles/bilingual.srt  # 应为空（除了刻意保留的）
```

**前 10 条必须回读**。术语不一致在成片上是灾难级的观感问题，而它只在抽查时暴露。

## 6. 竖屏 / 短视频

```bash
videocaptioner synthesize "$IN" -s subtitles/bilingual.srt \
  --subtitle-mode hard --quality high --style vertical \
  --style-override '{"margin_bottom": 340}' \
  --layout source-above -o "$OUT"
```

竖屏要同时调三样：字号（预设 78）、底距（≥320 避开抖音/视频号的按钮区）、
中文行宽（降到 ≤ 12 字，否则会顶到两侧）。

## 7. 长视频（>10 分钟）

瓶颈不在 ASR，在**模型一次处理几百条会掉质量**。做法是分批，但术语只定一次。

```bash
# 拆完先看总条数
python scripts/segments.py extract subtitles/src.srt -o work/seg.json

# 按 100～150 条切分（脚本不切，用 python 分片即可）
python - <<'PY'
import json
d = json.load(open('work/seg.json', encoding='utf-8'))
segs = d['segments']
for n, i in enumerate(range(0, len(segs), 120)):
    json.dump({'_note': d['_note'], 'count': len(segs[i:i+120]), 'segments': segs[i:i+120]},
              open(f'work/seg_{n}.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'work/seg_{n}.json  {len(segs[i:i+120])} 条')
PY
```

每批译文写一个 `dst_{n}.json`，最后按批 merge 再拼接。**拼接必须用 `segments.py concat`，
不要用 `cat`**——每个分片的编号都从 1 开始，且第 2 个分片的 BOM 会落到文件中间，
部分播放器会把那三个字节渲染成乱码方块：

```bash
for n in 0 1 2; do
  python scripts/segments.py merge work/seg_$n.json --dst work/dst_$n.json \
    -o work/part_$n.srt
done

# 重新编号 + 只保留开头一个 BOM；分片顺序错位时它会告警
python scripts/segments.py concat work/part_*.srt -o subtitles/bilingual.srt
```

`concat` 会检查时间轴是否单调递增，所以 `part_10` 被 shell 排到 `part_2` 前面这种事
能当场发现，不会一路做到成片才暴露。

ASR 阶段可以加 `--thread-num 8 --batch-size 40` 提速（默认 4 / 20）。

## 8. 已有双语字幕要微调

不要重跑整条链路。`dst.json` 是唯一需要改的文件：

```bash
# 改完 dst.json 直接重新合并，时间码不会变
python scripts/segments.py merge work/seg.json --dst work/dst.json \
  -o subtitles/bilingual.srt
# 再烧一次
videocaptioner synthesize "$IN" -s subtitles/bilingual.srt \
  --subtitle-mode hard --quality high --style default --layout source-above -o "$OUT"
```

如果只改了译文措辞而画面不动，可以跳过烧录，直接把新 srt 交给用户。

## 9. 双交付（成片 + 可上传字幕文件）

同一份 srt 出两种封装，省一次 ASR：

```bash
# 硬字幕成片（自己发布用）
videocaptioner synthesize "$IN" -s subtitles/bilingual.srt \
  --subtitle-mode hard --quality high --style default --layout source-above -o "$OUT"

# 软字幕轨（平台投稿用，观众可开关）
videocaptioner synthesize "$IN" -s subtitles/bilingual.srt \
  --subtitle-mode soft -o "${OUT%.mp4}_soft.mp4"
```

## 10. ASR 错词特别多的素材

免费引擎（bijian / jianying）对连读、人名、专有名词错误率不低，实测一小段预告里
5 条错 3 条。三种处理，按成本从低到高：

1. **在 dst.json 里顺手改 `src`**：`{"1": {"dst": "你害怕吗，士兵？", "src": "Are you afraid, soldier?"}}`。
   merge 会打印「已应用 N 条原文纠正」，最省事。
2. **换 ASR**：`--asr whisper-api`（需 key）或 `--asr whisper-cpp`（本地模型，慢但准）。
3. **给转写指定源语言**：`transcribe --language en`，避免引擎在小语种之间摇摆。
   注意 `transcribe` **没有 `--prompt` 参数**（1.4.2 实测），别照搬 `subtitle` 的参数。

## 11. 断句不合格要返工

`audit` 把有问题的条目直接列出来，不用肉眼过几百条：

```bash
python scripts/segments.py audit work/seg.json          # 转写刚拆完时看
python scripts/segments.py audit subtitles/bilingual.srt  # 交付前再确认一次
```

```
[*] 检查 38 条：32 条正常，0 条疑似碎片，6 条过长
[!] 过长（建议拆成数组，或缩短译文）：
    #2   5.31s  11 词/字  建议拆 2 段  'The tameless nature the story i came to '
```

三种处理，全部只改 `dst.json`、不碰时间码：

| audit 报的 | dst.json 写法 |
| --- | --- |
| 疑似碎片（< 0.8s，或只有一个词且极短） | `"5": "__MERGE_PREV__"`，时间并入上一条 |
| 过长（> 5s，或中文 > 18 字 / 英文 > 14 词） | `"2": {"src": ["前半句", "后半句"], "dst": ["译文一", "译文二"]}` |
| 一句话被 ASR 切成两条 | 上条写合并后的完整文本，下条标 `"__MERGE_PREV__"` |

拆分的时长由 `merge` 按各段原文字数比例分配，不用手算。拆完再跑一次
`audit` 确认清零——反复几次直到只剩软性告警。

**判据别调太紧**：`They're amazing`（1.2 秒、2 词）是完整短句，不该报碎片；
2 秒内 15 个词的快语速预告也不该硬拆，那会让每段都不到 1 秒。
