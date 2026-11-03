# 技能上架开发计划

> 本文件是仓库级开发路线图，回答「现在有哪些技能可以上架、接下来做什么」。
> 以各技能 `SKILL.md` 的 `version` 为唯一真源；已发布版本见 `git tag`。

---

## 一、现状盘点

当前 `skills/` 下只有一个技能，完成度如下：

| 技能 | 版本 | 可上架？ | 卡点 |
|---|---|---|---|
| [`bilingual-subtitle`](skills/bilingual-subtitle/SKILL.md) | `1.1.2` | ✅ 技术面就绪，只差一步 | `author` 仍是占位符「个人开发者」 |

**技术面已经就绪的证据**（`python build/pack.py check` 实跑结果）：

- 8 个 frontmatter 字段齐全且非空；
- 目录白名单通过（`SKILL.md` + `references/` + `scripts/` + `templates/`，共 14 个文件）；
- `version` 与 `CHANGELOG.md` 顶部条目一致；
- 已打过三个 tag：`v1.1.0` / `v1.1.1` / `v1.1.2`。

**唯一的硬阻塞**：`author` 还是 `"个人开发者"`。`check` 只提醒，`pack` 会直接中止
（除非 `--allow-placeholder`，仅限本地试打包）。上架前必须换成真实入驻主体名。

结论：**现在能上架的就是 `bilingual-subtitle` 一个，且只差 `author` 这一个字段。**

---

## 二、可上架清单

### 立即可上架

- **`bilingual-subtitle` v1.1.2** —— 外语视频 → 双语字幕成片（本地 Whisper 转写 → 断句 →
  模型翻译 → 烧录/封装 → 验收），自带 5 个脚本 + 4 个样式预设 + 3 份参考文档。

### 暂不可上架（尚未开发）

仓库目前没有第二个技能。以下方向可供后续规划，但**均为「想做未做」，不等于现状**：

| 候选方向 | 一句话定位 | 与现有技能的边界 |
|---|---|---|
| 字幕后续环节（如多语种硬/软字幕批处理、字幕时间轴校对） | 可能并入 `bilingual-subtitle`，而非新技能 | 若触发词重叠会导致加载错技能，需先评估 |
| 视频剪辑/抽帧类 | 与字幕技能解耦的独立场景 | 无重叠，可独立成技能 |

> 加新技能前先读 `AGENTS.md` 第 4 节「触发条件不与其他技能重叠」。

---

## 三、`bilingual-subtitle` 上架执行计划

按 `docs/publish.md` 的七步流程拆解，已完成的标注状态：

| # | 动作 | 状态 | 说明 |
|---|---|---|---|
| 1 | 注册入驻，拿到主体名 | ⬜ 待办 | 主体名就是填进 `author` 的名字 |
| 2 | 资质认证 | ⬜ 待办 | 认证通过前提交会被退回 |
| 3 | 创建应用，类型选「技能」 | ⬜ 待办 | 选错类型要重走 |
| 4 | 替换 `author` 字段 | ⬜ 待办 | `skills/bilingual-subtitle/SKILL.md` 第 22 行 |
| 5 | 重跑 `check` + `pack` | ✅ 可随时 | 见下方命令 |
| 6 | 上传 zip 提交审核 | ⬜ 待办 | 用 `build/out/*.zip`，不要手动压缩 |
| 7 | 发布上线 + 版本维护 | ⬜ 待办 | 后续更新重复 4–7 步 |

**关键操作命令**（`author` 定稿后执行）：

```bash
# 1. 改 author（把 个人开发者 换成真实主体名）
#    skills/bilingual-subtitle/SKILL.md 的 author 字段

# 2. 合规检查 + 打包
python build/pack.py check skills/bilingual-subtitle
python build/pack.py pack  skills/bilingual-subtitle

# 3. 提交（只暂存本次改动）
git add skills/bilingual-subtitle/SKILL.md skills/bilingual-subtitle/CHANGELOG.md
git commit -m "chore(bilingual-subtitle): author 替换为入驻主体名"

# 4. 若版本号有变则打 tag（本步为改 author，通常不改版本号）
```

> 改 `author` 属于元信息修正，通常不 bump 版本号、不打新 tag。

---

## 四、后续迭代方向（`bilingual-subtitle`）

| 优先级 | 方向 | 触发点 |
|---|---|---|
| P1 | 补充软字幕（`--subtitle-mode soft`）的更多实测案例 | 用户反馈软字幕场景问题 |
| P2 | 扩大语言对覆盖的坑表（非中英语对） | 遇到非英语视频 |
| P3 | 低置信复听流程工具化（`--hotwords` 交互） | 转写错误率高的素材 |

迭代纪律（见 `AGENTS.md`）：

- 改技能就要动 `version` + 更新 `CHANGELOG.md` 顶部条目，两者一致；
- 一次提交只做一件事；不 `git add -A`；
- 只写实测过的参数，没跑通就留 TODO。

---

## 五、新技能孵化流程（候选方向落地时）

```bash
mkdir -p skills/<name>/{scripts,references}
# 写 SKILL.md：8 个字段齐全，name 与目录名一致（小写字母/数字/连字符）
# 只允许 SKILL.md / references/ / scripts/ / templates/
```

新技能从「想法」到「可上架」的里程碑：

1. **定义边界**：与 `bilingual-subtitle` 的触发词不重叠（`AGENTS.md` 第 4 节）；
2. **最小可用**：SKILL.md 骨架 + 一个能跑通的脚本；
3. **实测通过**：真跑一遍，不是只看代码；
4. **过三关**：`check` → `pack` → 真机验证，`author` 用真实主体名；
5. **发布**：走 `docs/publish.md` 七步，打 tag `<name>-v<version>`。

---

## 六、当前阻塞汇总（唯一待办）

- [ ] `skills/bilingual-subtitle/SKILL.md` 的 `author` 仍是 `"个人开发者"`，上架前必须换成入驻主体名
  （与 `AGENTS.md`「当前待办」一致）
