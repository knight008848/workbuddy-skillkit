# WorkBuddy 技能仓库

自建 WorkBuddy 技能的开发与发布仓库。`skills/` 下每个目录是一个可独立打包上架的技能，
版本互不干扰——一个技能发新版不会牵连其他技能。

## 目录职责

| 路径 | 作用 | 入库 |
|---|---|---|
| `skills/<name>/` | 技能源码，**唯一可发布产物的来源** | ✅ |
| `skills/<name>/CHANGELOG.md` | 该技能的变更记录 | ✅ 但不进 zip |
| `build/pack.py` | 合规检查 + 打包 | ✅ |
| `build/link.py` | 链接进 WorkBuddy 用户技能目录，便于测试 | ✅ |
| `build/out/` | 生成的 zip | ❌ 可随时重打 |
| `dev/input/` | 测试视频 | ❌ |
| `dev/work/`、`dev/output/` | 转写中间产物、成片、抽帧 | ❌ |
| `dev/archive/` | 历史版本快照（git 之前的手工备份） | ❌ |
| `docs/source/` | 原始稿件 | ✅ |
| `tests/fixtures/` | 少量文本样例（JSON / srt），可复现 | ✅ |

**为什么 `dev/` 不入库**：测试素材是 275MB 的二进制视频，且每次跑流程都在变。放进去只会让仓库不可克隆、
让 `git status` 永远脏。技能源码总共才 120KB，仓库保持这个量级才有意义。

## 日常流程

```bash
# 1. 直接改 skills/<name>/ 下的文件

# 2. 挂到 WorkBuddy 里实测（只需执行一次，之后改文件即时生效）
python build/link.py link bilingual-subtitle
#    重启会话后生效。不链接只复制的话，改完 A 测试 B 是「改了没生效」的头号原因

# 3. 合规检查（对照技能市场的 8 个字段与目录白名单）
python build/pack.py check skills/bilingual-subtitle

# 4. 打包，产物在 build/out/<name>-<version>.zip，zip 内根目录为 <name>/
python build/pack.py pack skills/bilingual-subtitle

# 5. 提交 + 打 tag（版本号与 tag 必须对应）
git add -A && git commit -m "feat(bilingual-subtitle): 新增本地 Whisper 转写"
git tag bilingual-subtitle-v1.1.0
```

上传步骤见 [docs/publish.md](docs/publish.md)。

## 版本约定

**`SKILL.md` 的 `version` 是唯一真源**。`CHANGELOG.md` 顶部条目的版本必须与之一致，`pack.py check` 会核对，
不一致会提醒你。

| 变更 | 版本位 | 例子 |
|---|---|---|
| 修错字、调阈值、补坑表 | patch | `1.1.0` → `1.1.1` |
| 新增脚本 / 子命令 / 流程步骤 | minor | `1.0.0` → `1.1.0` |
| 流程结构变了，老用法失效 | major | `1.x` → `2.0.0` |

**tag 格式：`<技能名>-v<版本>`**，例如 `bilingual-subtitle-v1.1.0`。
加技能名前缀是因为一个仓库有多个技能，只写 `v1.1.0` 会分不清是谁的版本。

## 提交信息

`type(scope): 中文摘要`

- `type` 取 `feat` / `fix` / `docs` / `chore` / `refactor` / `test`
- `scope` 是技能名，跨技能的改动可省略

```
feat(bilingual-subtitle): 新增本地 Whisper 转写入口
fix(bilingual-subtitle): 修正 --sentence 只作用于 srt 的说明
docs: 补充上架驳回清单
```

## 新增一个技能

```bash
mkdir -p skills/my-skill/{scripts,references}
```

然后写 `SKILL.md`，frontmatter 必须有这 8 个字段（缺一个就会被市场驳回）：

```
name / display_name / display_name_en / description / description_zh / description_en / version / author
```

几条硬约束：

- `name` 必须**与目录名完全一致**，且只用小写字母、数字、连字符（`pack.py` 会核对）
- 目录里只允许 `SKILL.md`、`references/`、`scripts/`、`templates/`；其他目录名一律不进 zip
  （曾因把字体预设放在 `assets/` 里被拦下过，现在打包前就会报错）
- 不要在技能目录里放测试视频、生成的 srt、`__pycache__`

## 有意不做的事

- **不把 zip 提交入库**：它是从 `skills/` 生成的产物，入库只会产生「源码没变但 zip 变了」的假改动
- **不把测试视频放仓库**：一律放 `dev/input/`
- **不建 dev 分支**：单人维护走主干开发，`main` 始终可发布；实验性改动直接开短分支，合完就删
