# AGENTS.md

本仓库的 AI 协作约束。**动手前先读完第 1、6 两节**——那里每一条都对应一次真实返工。

---

## 0. 先分清你在改什么

| 要做的事 | 改哪里 | 不要碰 |
|---|---|---|
| 技能行为、提示词、脚本 | `skills/<name>/` | `dev/` 里的历史产物 |
| 某个版本改了什么 | `skills/<name>/CHANGELOG.md` | 已发布的 tag |
| 构建与校验逻辑 | `build/pack.py` | 不要为个别技能开特例 |
| 流程说明 | `README.md`、`docs/` | — |

一个技能的改动**不应该**影响另一个技能。如果你的改动需要同时动两个技能，先确认它们是不是本来就该合并。

---

## 1. 硬约束（违反会被技能市场驳回）

1. **frontmatter 必须有 8 个字段且非空**：`name` `display_name` `display_name_en`
   `description` `description_zh` `description_en` `version` `author`
2. **`name` 必须与目录名完全一致**，只用小写字母、数字、连字符
3. **目录里只允许** `SKILL.md`、`references/`、`scripts/`、`templates/`。
   `assets/`、`examples/` 一律不行——曾把字体预设放在 `assets/` 里被驳回，迁到 `templates/` 才过
4. **`author` 必须是真实入驻主体名**。`个人开发者` 是占位符，`pack.py pack` 会直接拒绝
5. **zip 根目录必须是 `<name>/`**。不要手动右键压缩，会多套一层导致「装了没反应」
6. `CHANGELOG.md` 是例外：可以放在技能目录里就近维护，但**不进 zip**

以上全部由 `build/pack.py check` 自动核对，**不要靠眼睛看**。

---

## 2. 改技能的固定动作

```bash
# 1) 改 skills/<name>/ 下的文件
# 2) 实测 —— 必须真跑一遍，不能只看代码
python build/link.py link <name>          # 只需一次，之后改文件即时生效
# 3) 校验
python build/pack.py check skills/<name>
# 4) 打包
python build/pack.py pack skills/<name>
```

**版本与文档必须同步**：改技能就要动 `version`，并在 `CHANGELOG.md` 顶部加对应版本条目。
两边不一致时 `pack.py` 会提醒。

| 改了什么 | 版本位 |
|---|---|
| 修错字、调阈值、补坑表 | patch |
| 新增脚本 / 子命令 / 流程步骤 | minor |
| 流程结构变了，老用法失效 | major |

---

## 3. 写脚本的约定

这些脚本是**给模型执行、给用户排错**用的，不是给人读的产品代码。

- **零依赖**：只用标准库。用户机器上未必有 venv，`requests` / `pyyaml` 都可能没装
- **不硬编码绝对路径**：按「参数 → 环境变量 → 默认位置 → PATH」四级探测，缺什么就报什么，
  不要静默失败
- **退出码分级**，别只返回 0/1：
  - `0` 通过
  - `3` 校验失败或输入不合规
  - `4` 依赖缺失或路径不存在
- **幂等**：重复执行结果一致；写文件前自己建目录
- **只写自己该写的地方**：不要在技能目录外留缓存或临时文件
- **反向测一次**：写校验逻辑时，故意造一个不合规的输入，确认它真的会拦下来

`build/link.py` 是正面例子：Windows 用 junction 而不是复制，`unlink` 只摘链接、不删源目录。

---

## 4. 写 SKILL.md 的约定

- **只写实测过的**。没跑通的参数不要写进去，宁可留 TODO
- **写清触发条件**：什么时候该用、什么时候不该用。触发词要覆盖用户真实说法，
  但**避免与同域技能重叠**——重叠会导致加载错技能
- **坑表比教程重要**：一张「症状 → 原因 → 怎么办」的表，比大段原理有用
- **长表格放 `references/`**：SKILL.md 保持一屏能读完的骨架，细节展开到 `references/`，
  并明确写「只在需要精确参数时读」
- **不写营销话术**：不要「强大、高效、一站式」

---

## 5. Git 与发布

- 提交信息：`type(scope): 中文摘要`，`type` 取 `feat` / `fix` / `docs` / `chore` / `refactor` / `test`
- **tag 只在发布时打**，格式 `<技能名>-v<版本>`；已推送的 tag 不要移动或改写
- 发布流程见 `docs/publish.md`
- **删技能前先解依赖**：先搜其他技能里有没有「见 xxx 技能」这类交叉引用，
  把要保留的内容迁走再删。删 `videocaptioner` 时就是先把它的 CLI 全表迁进
  `bilingual-subtitle/references/`，否则会留下悬空引用

---

## 6. 本机环境坑（每一条都咬过人）

| 现象 | 原因 | 处理 |
|---|---|---|
| 技能 zip 里混进 CRLF | 系统级 `core.autocrlf=true`，`rebase` / `checkout` 会重写工作区 | 本仓库已设 `core.autocrlf=false`；改完文件用 `git ls-files --eol` 确认全是 `w/lf` |
| `git status` 显示 `M`，但 `git diff --stat` 为空 | 索引里的 stat 缓存过期（大小变了、内容没变） | `git add -A` 刷新即可，**不要**当成真改动去提交 |
| `git push` 报 502 / TLS handshake / Could not connect | 本机到 GitHub 链路间歇失败，与凭据无关 | 重试；交替「走代理」与 `-c http.proxy= -c https.proxy=` 直连 |
| 非交互执行 git 卡住 | GCM 弹了登录窗 | 加 `GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never` |
| `rmdir` 报「目录非空」但 `ls` 是空的 | Windows 文件系统延迟 | 重试一次即可 |

---

## 7. 禁止事项

- ❌ 把 `dev/` 里的视频、成片、抽帧提交入库
- ❌ 把 `build/out/*.zip` 提交入库——它是产物，可重打
- ❌ 提交 `__pycache__`
- ❌ 为了让检查通过去放宽 `pack.py` 的白名单。**要改的是技能，不是尺子**
- ❌ 在 `SKILL.md` 里写没验证过的参数或行为
- ❌ 移动或改写已发布的 tag

---

## 8. 收尾自检

```bash
python build/pack.py check skills/<name>   # 字段、白名单、版本一致性
python build/pack.py pack  skills/<name>   # 能出包
git ls-files --eol | grep w/crlf           # 应为空
git status --porcelain                     # 应只含本次改动的文件
git diff --stat                            # 若与 status 不一致，是 stat 缓存
```

五项都过，再提交。

---

## 当前待办

- [ ] `skills/bilingual-subtitle/SKILL.md` 的 `author` 仍是 `"个人开发者"`，上架前必须换成入驻主体名
- [ ] `docs/source/videocaptioner-原始稿件.md` 是否保留待定
