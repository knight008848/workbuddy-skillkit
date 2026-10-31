# AGENTS.md

本仓库的 AI 协作约束。**动手前先读完第 1、6 两节**——那里每一条都对应一次真实返工。

---

## 0. 先分清你在改什么

| 要做的事 | 改哪里 | 不要碰 |
|---|---|---|
| 技能行为、提示词、脚本 | `skills/<name>/` | `dev/` 里的历史产物 |
| 某个版本改了什么 | `skills/<name>/CHANGELOG.md` | 已发布的 tag |
| 构建与校验逻辑 | `build/pack.py` | 不要为个别技能开特例 |
| 流程说明、目录结构、用法 | `README.md`、`docs/` | 见 5.3：改完必须同步，不能只改代码 |

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

## 5. Git、文档与发布

### 5.1 提交信息与 tag

- 提交信息：`type(scope): 中文摘要`，`type` 取 `feat` / `fix` / `docs` / `chore` / `refactor` / `test`
- **tag 只在发布时打**，格式 `<技能名>-v<版本>`；已推送的 tag 不要移动或改写
- 发布流程见 `docs/publish.md`

### 5.2 一次提交只做一件事

**判据**：如果摘要需要用「和 / 顺便 / 同时 / 另外」把两件事连起来，就该拆成两个提交。

| 应该在一起 | 应该拆开 |
|---|---|
| 技能改动 + 它的 `version` + 它的 `CHANGELOG` 条目 | 改技能 + 改 `build/pack.py` |
| 改 `pack.py` + 为它补的反向测试 | 修技能 A + 修技能 B（除非本来就该合并） |
| 删技能 + 迁移它承载的内容 + 改引用 | 文档更新 + 无关的格式化/换行符归一 |
| 同一处逻辑的连续修正（写错了再改） | 「顺手」清理的无关文件 |

为什么必须这样：

1. **能回滚**。技能改动和版本号分两次提交，中间那个状态**打不出包**，
   回滚就只能回滚一半，回到一个既不能发也不能跑的点
2. **能定位**。混提交出问题时，只能整体回退再重做一遍
3. **能读懂历史**。`git log` 每行一件事，才能回答「这版为什么变了」

反过来的错误同样要避免：**同一文件的同一处改动不要为凑数硬拆**。
把「补两条约束」拆成两个提交，是形式上的原子化，只会让历史变长。

提交前用 `git status` 核对暂存清单，只 `git add` 本次要提交的文件，
**不要习惯性 `git add -A`** —— 它会把 `dev/` 里新生成的产物、
改到一半的草稿一并卷进来。

### 5.3 README 必须与项目现状一致

README 是别人（和三个月后的你）进仓库看的第一份东西，**它写的每一行都要能当场验证**：

- **目录树**：随目录增删同步更新。删了技能就删对应行，不要留着「以后可能会加」
- **技能清单与示例命令**：每个路径必须真实存在，每条命令必须能直接复制执行
- **快速开始**：命令改了就重跑一遍。写 `python build/pack.py` 却实际要传
  `skills/<name>`，等于没写
- **不写死版本号、文件数、体积**：这些每改一次就过时，需要时让工具输出
- **不写计划当现状**：想做但没做的不进 README，进 issue 或本文末尾的待办
- **不要出现已删除的技能名**：删 `videocaptioner` 时，README 里
  「一个仓库放多个技能（发 `bilingual-subtitle` 的新版不影响 `videocaptioner`）」
  这句话就必须一起改，否则文档比代码还可信度低

**改动技能或工具链后，顺手核对一遍 README 的对应段落**——不是重写整篇，
只改被这次改动影响到的那几句。这份检查不靠肉眼：

```bash
# README 提到的路径必须存在（「新增一个技能」示例里的 my-skill 会命中，属正常）
grep -oE 'skills/[a-z0-9-]+' README.md | sort -u | while read p; do
  [ -d "$p" ] || echo "README 指向不存在的目录: $p"; done
# 反向：仓库里的技能都要在 README 出现，不能漏写
ls -d skills/*/ | while read d; do n=$(basename "$d")
  grep -q "$n" README.md || echo "README 漏写技能: $n"; done
```

### 5.4 删技能前先解依赖

先搜其他技能里有没有「见 xxx 技能」这类交叉引用，把要保留的内容迁走再删。
删 `videocaptioner` 时就是先把它的 CLI 全表迁进 `bilingual-subtitle/references/`，
否则会留下悬空引用。

---

## 6. 本机环境坑（每一条都咬过人）

| 现象 | 原因 | 处理 |
|---|---|---|
| **改了技能，WorkBuddy 里跑的仍是旧版** | `~/.workbuddy/skills/<name>` 是**手工副本**而不是链接，`link.py list` 显示 `[实体]`。曾出现装的是 1.0.0、仓库已到 1.1.1，`asr.py` 在会话里根本不存在 | 先把副本挪到 `dev/archive/`，再 `python build/link.py link <name>`；`link.py` 会拒绝在真实目录上动手，这是有意的保护 |
| 技能 zip 里混进 CRLF | 系统级 `core.autocrlf=true`，`rebase` / `checkout` 会重写工作区 | 本仓库已设 `core.autocrlf=false`；改完文件用 `git ls-files --eol` 确认全是 `w/lf` |
| `git status` 显示 `M`，但 `git diff --stat` 为空 | 索引里的 stat 缓存过期（大小变了、内容没变） | `git add -A` 刷新即可，**不要**当成真改动去提交 |
| `git push` 报 502 / TLS handshake / Could not connect | 本机到 GitHub 链路间歇失败，与凭据无关。若走代理时 `api.github.com` 返回 200 而 `github.com` 返回 502，那是代理的分域规则，不是仓库问题 | 重试；交替「走代理」与 `-c http.proxy= -c https.proxy=` 直连（两种都会时通时不通，实测直连常在 502 之后成功） |
| 非交互执行 git 卡住 | GCM 弹了登录窗 | 加 `GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never` |
| `rmdir` 报「目录非空」但 `ls` 是空的 | Windows 文件系统延迟 | 重试一次即可 |
| `gh auth login --with-token` 报 `missing required scope 'read:org'` | GCM 缓存的是 40 位 classic PAT，没有 `read:org`；gh 登录校验要求它 | 别登录。bash 里**直接 `gh`** 即可（`~/bin/gh` 包装，Git Bash 会把 `~/bin` 自动加进 PATH）；不在 bash 场景用 `bash build/gh.sh`。两者都只是运行时注入 `GH_TOKEN`，token 不落盘 |
| PowerShell / cmd 里 `gh` 找不到 | `~/bin` 是 Git Bash 的约定，**不在 Windows PATH**；`.cmd` 版包装已试过并放弃：GBK 控制台中文乱码、`for /f` 读 `git credential` 不稳 | 需要 gh 时就开 bash；不要在 PowerShell 里绕。要真覆盖，得改用户级 PATH，收益不值 |
| 从 GitHub 下载 release 资产极慢或超时 | 302 跳到 `objects.githubusercontent.com`（185.199.x.x），直连超时、走代理约 3 KB/s | 用镜像前缀：`https://gh-proxy.com/https://github.com/...`（实测约 1–9 MB/s），配合 `-C -` 断点续传 |

---

## 7. 禁止事项

- ❌ 把 `dev/` 里的视频、成片、抽帧提交入库
- ❌ 把 `build/out/*.zip` 提交入库——它是产物，可重打
- ❌ 提交 `__pycache__`
- ❌ 用 `git add -A` 图省事。只暂存本次该提交的文件，避免把产物和草稿卷进来
- ❌ 把两件不相干的事塞进同一次提交（判据见 5.2）
- ❌ README 里留着已删除的目录、已改名的命令、已过时的版本号（见 5.3）
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
grep -oE 'skills/[a-z0-9-]+' README.md | sort -u   # 与 ls skills/ 对照，应一致
```

六项都过，再提交。提交前再看一眼 `git status`：**里面的文件是不是都该在同一次提交里**。

---

## 当前待办

- [ ] `skills/bilingual-subtitle/SKILL.md` 的 `author` 仍是 `"个人开发者"`，上架前必须换成入驻主体名
